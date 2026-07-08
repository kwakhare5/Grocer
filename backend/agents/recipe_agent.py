"""
Recipe Suggestion Agent — Task 4.1 & 4.2
Stateful one-shot agent for parsing recipes, evaluating estimated pantry states,
detecting missing items, and preparing a PreFill checkout cart.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.mcp.client import mcp_client
from backend.database.models import Household, ConsumptionModel

from backend.agents.llm_client import get_llm
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class RecipeState(TypedDict):
    db: AsyncSession
    household_id: str  # user_id string (e.g. 'demo_user_001')
    recipe_name: str
    servings: int
    household_uuid: Optional[uuid.UUID]
    parsed_ingredients: List[Dict[str, Any]]
    pantry_items: List[Dict[str, Any]]
    you_have: List[Dict[str, Any]]
    you_need: List[Dict[str, Any]]
    missing_items: List[Dict[str, Any]]
    cart_items: List[Dict[str, Any]]
    cart_id: Optional[str]
    estimated_cost: float
    ready_to_cook: bool

class ParsedIngredient(BaseModel):
    name: str = Field(description="The standard Indian grocery app name of the ingredient")
    quantity: float = Field(description="The numeric quantity needed")
    unit: str = Field(description="The unit (g, kg, ml, L, piece, tbsp, tsp)")

class RecipeIngredients(BaseModel):
    ingredients: List[ParsedIngredient]


# ---------------------------------------------------------------------------
# Helpers for Unit Conversion and Fuzzy Matching
# ---------------------------------------------------------------------------

def normalize_quantity(qty: float, unit: str) -> float:
    """Normalize to standard units: kg for solids, L for liquids, pieces for counts."""
    u = unit.lower().strip()
    if u in ['g', 'gram', 'grams']:
        return qty / 1000.0
    if u in ['ml', 'milliliter', 'milliliters']:
        return qty / 1000.0
    if u in ['tsp', 'teaspoon', 'teaspoons']:
        return (qty * 5.0) / 1000.0
    if u in ['tbsp', 'tablespoon', 'tablespoons']:
        return (qty * 15.0) / 1000.0
    return qty


def find_pantry_match(ingredient_name: str, pantry_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Fuzzy match ingredient name to closest pantry item in our modeled list."""
    ing_lower = ingredient_name.lower().strip()
    best_match = None
    best_score = 0.0

    for item in pantry_items:
        item_name_lower = item["item_name"].lower()

        # Exact match
        if ing_lower == item_name_lower:
            return item

        # Substring matches
        if ing_lower in item_name_lower or item_name_lower in ing_lower:
            score = min(len(ing_lower), len(item_name_lower)) / max(len(ing_lower), len(item_name_lower))
            if score > best_score:
                best_score = score
                best_match = item

    # Token overlap match if substring score is low
    if best_score < 0.4:
        ing_tokens = set(ing_lower.split())
        for item in pantry_items:
            item_name_lower = item["item_name"].lower()
            item_tokens = set(item_name_lower.split())
            intersection = ing_tokens.intersection(item_tokens)
            if intersection:
                score = len(intersection) / len(ing_tokens.union(item_tokens))
                if score > best_score:
                    best_score = score
                    best_match = item

    if best_score >= 0.2:
        return best_match

    return None


# ---------------------------------------------------------------------------
# Graph Node Implementations
# ---------------------------------------------------------------------------

async def parse_recipe_node(state: RecipeState) -> RecipeState:
    """Uses Claude API to extract clean, standard Indian ingredients from recipe name."""
    recipe_name = state["recipe_name"]
    servings = state["servings"]

    prompt = f"""List all ingredients needed for "{recipe_name}" for {servings} people.
Use standard Indian grocery app names (e.g. "basmati rice" not "long-grain rice", "onions" instead of "red onions").
Units must be: g, kg, ml, L, piece, tbsp, tsp.
"""

    try:
        llm = get_llm().with_structured_output(RecipeIngredients)
        parsed: RecipeIngredients = await llm.ainvoke([HumanMessage(content=prompt)])
        state["parsed_ingredients"] = [i.model_dump() for i in parsed.ingredients]
    except Exception as e:
        logger.error(f"Failed to parse recipe ingredients: {e}")
        state["parsed_ingredients"] = []

    return state


async def check_pantry_node(state: RecipeState) -> RecipeState:
    """Fetches and calculates current estimated pantry quantities based on consumption rates."""
    db = state["db"]
    household_id = state["household_id"]

    try:
        # Resolve household user_id to UUID
        stmt = select(Household).where(Household.user_id == household_id)
        res = await db.execute(stmt)
        hh = res.scalar_one_or_none()

        if not hh:
            logger.warning(f"Household not found for user: {household_id}")
            state["pantry_items"] = []
            return state

        state["household_uuid"] = hh.id  # type: ignore

        # Retrieve consumption models
        stmt_models = select(ConsumptionModel).where(ConsumptionModel.household_id == hh.id)
        res_models = await db.execute(stmt_models)
        models = res_models.scalars().all()

        pantry_list = []
        now = datetime.now(timezone.utc)

        for m in models:
            estimated_remaining = 0.0
            if m.last_purchase_date is not None and m.last_purchase_quantity is not None:
                lp_date = m.last_purchase_date
                if lp_date.tzinfo is None:
                    lp_date = lp_date.replace(tzinfo=timezone.utc)
                
                days_elapsed = (now - lp_date).total_seconds() / 86400.0
                if days_elapsed < 0:
                    days_elapsed = 0.0
                
                rate = m.avg_daily_consumption or 0.0
                estimated_remaining = max(0.0, m.last_purchase_quantity - (rate * days_elapsed))

            pantry_list.append({
                "item_id": m.item_id,
                "item_name": m.item_name,
                "category": m.category,
                "estimated_remaining": estimated_remaining,
            })

        state["pantry_items"] = pantry_list
    except Exception as e:
        logger.error(f"Failed to evaluate pantry state: {e}")
        state["pantry_items"] = []

    return state


async def identify_missing_node(state: RecipeState) -> RecipeState:
    """Compares ingredients needed vs estimated pantry state and flags missing items."""
    parsed_ingredients = state["parsed_ingredients"]
    pantry_items = state["pantry_items"]

    you_have = []
    you_need = []
    missing_items = []

    for ing in parsed_ingredients:
        needed_qty = float(ing.get("quantity", 0))
        unit = ing.get("unit", "piece")
        needed_norm = normalize_quantity(needed_qty, unit)

        match = find_pantry_match(ing["name"], pantry_items)

        if match:
            # Match found, check if we have enough remaining
            pantry_qty = match["estimated_remaining"]  # already in standard units (L, kg, pieces)
            if pantry_qty >= needed_norm:
                you_have.append({
                    "name": ing["name"],
                    "quantity": needed_qty,
                    "unit": unit,
                    "estimated": f"{pantry_qty:.2f} standard units left"
                })
            else:
                you_need.append({
                    "name": ing["name"],
                    "quantity": needed_qty,
                    "unit": unit,
                })
                missing_items.append({
                    "name": match["item_name"],  # use catalog name
                    "quantity": needed_qty,
                    "unit": unit,
                    "matched": True
                })
        else:
            # No matching item in pantry models
            you_need.append({
                "name": ing["name"],
                "quantity": needed_qty,
                "unit": unit,
            })
            missing_items.append({
                "name": ing["name"],
                "quantity": needed_qty,
                "unit": unit,
                "matched": False
            })

    state["you_have"] = you_have
    state["you_need"] = you_need
    state["missing_items"] = missing_items
    state["ready_to_cook"] = (len(missing_items) == 0)
    return state


async def search_items_node(state: RecipeState) -> RecipeState:
    """Searches the PreFill catalog for each missing item to find standard products and prices."""
    missing_items = state["missing_items"]
    cart_items = []
    estimated_cost = 0.0

    for item in missing_items:
        try:
            res = await mcp_client.search_platform_items(item["name"])
            catalog_items = res.get("items", [])
            if catalog_items:
                best_match = catalog_items[0]
                cart_items.append({
                    "item_id": best_match["id"],
                    "item_name": best_match["name"],
                    "quantity": 1,  # Standard: order 1 unit pack of the item
                    "price": float(best_match.get("price", 50.0))
                })
                estimated_cost += float(best_match.get("price", 50.0))
            else:
                # Fallback if no item matched in mock catalog
                cart_items.append({
                    "item_id": f"MOCK_{str(uuid.uuid4())[:8]}",
                    "item_name": f"{item['name']} (Standard Pack)",
                    "quantity": 1,
                    "price": 50.0
                })
                estimated_cost += 50.0
        except Exception as e:
            logger.error(f"Error searching item {item['name']}: {e}")
            cart_items.append({
                "item_id": f"MOCK_{str(uuid.uuid4())[:8]}",
                "item_name": f"{item['name']} (Standard Pack)",
                "quantity": 1,
                "price": 50.0
            })
            estimated_cost += 50.0

    state["cart_items"] = cart_items
    state["estimated_cost"] = round(estimated_cost, 2)
    return state


async def build_cart_node(state: RecipeState) -> RecipeState:
    """Calls PreFill MCP update cart endpoint to populate the checkout basket."""
    cart_items = state["cart_items"]
    if not cart_items:
        state["cart_id"] = None
        return state

    try:
        items_payload = [
            {"item_id": item["item_id"], "quantity": item["quantity"]}
            for item in cart_items
        ]
        res = await mcp_client.update_platform_cart(items_payload)
        if res.get("success"):
            state["cart_id"] = res.get("cart_id")
            # Update estimated cost with official cart total if available
            if "total" in res:
                state["estimated_cost"] = float(res["total"])
        else:
            state["cart_id"] = None
    except Exception as e:
        logger.error(f"Failed to populate PreFill cart: {e}")
        state["cart_id"] = None

    return state


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

workflow = StateGraph(RecipeState)  # type: ignore

workflow.add_node("parse_recipe", parse_recipe_node)
workflow.add_node("check_pantry", check_pantry_node)
workflow.add_node("identify_missing", identify_missing_node)
workflow.add_node("search_items", search_items_node)
workflow.add_node("build_cart", build_cart_node)

workflow.set_entry_point("parse_recipe")
workflow.add_edge("parse_recipe", "check_pantry")
workflow.add_edge("check_pantry", "identify_missing")
workflow.add_edge("identify_missing", "search_items")
workflow.add_edge("search_items", "build_cart")
workflow.add_edge("build_cart", END)

recipe_graph = workflow.compile()


# ---------------------------------------------------------------------------
# Main Entry Point Function
# ---------------------------------------------------------------------------

async def recipe_to_cart(recipe_name: str, servings: int, household_id: str, db: AsyncSession) -> dict:
    """
    Stateful execution wrapper that runs the Recipe Graph from end to end.
    """
    initial_state: RecipeState = {
        "db": db,
        "household_id": household_id,
        "recipe_name": recipe_name,
        "servings": servings,
        "household_uuid": None,
        "parsed_ingredients": [],
        "pantry_items": [],
        "you_have": [],
        "you_need": [],
        "missing_items": [],
        "cart_items": [],
        "cart_id": None,
        "estimated_cost": 0.0,
        "ready_to_cook": False
    }

    try:
        final_state = await recipe_graph.ainvoke(initial_state)
        return {
            "recipe": final_state["recipe_name"],
            "servings": final_state["servings"],
            "you_have": final_state["you_have"],
            "you_need": final_state["you_need"],
            "cart_items": final_state["cart_items"],
            "cart_id": final_state["cart_id"],
            "estimated_cost": final_state["estimated_cost"],
            "ready_to_cook": final_state["ready_to_cook"]
        }
    except Exception as e:
        logger.error(f"Recipe agent execution failed: {e}")
        return {
            "recipe": recipe_name,
            "servings": servings,
            "you_have": [],
            "you_need": [],
            "cart_items": [],
            "cart_id": None,
            "estimated_cost": 0.0,
            "ready_to_cook": False,
            "error": str(e)
        }
