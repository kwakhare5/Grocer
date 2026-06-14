"""
Recipes API — Task 3.3 (frontend hydration)
Exposes stored recipe records for a household.

Endpoints:
  - GET /api/recipes/{user_id}   — list all pinned recipes
  - GET /api/recipes/             — index

Note on current state:
  The recipes table exists in the DB but recipe generation (via Claude AI)
  is a future enhancement (Backlog). For now, this endpoint returns what
  exists in the DB — if empty, the frontend shows an empty state gracefully.
  Recipe AI generation is planned as a post-Week-3 feature.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.connection import get_db
from backend.database.models import Household, Recipe

router = APIRouter(prefix='/api/recipes', tags=['recipes'])


async def _get_household(user_id: str, db: AsyncSession) -> Household:
    result = await db.execute(select(Household).where(Household.user_id == user_id))
    hh = result.scalar_one_or_none()
    if not hh:
        raise HTTPException(status_code=404, detail=f'Household not found for user: {user_id}')
    return hh


@router.get('/{user_id}')
async def get_recipes(user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return all saved recipes for a household, ordered by pinned_for date.
    Returns an empty list if none exist yet (recipe generation is backlog).
    """
    hh = await _get_household(user_id, db)

    result = await db.execute(
        select(Recipe)
        .where(Recipe.household_id == hh.id)
        .order_by(Recipe.pinned_for.desc().nullslast(), Recipe.created_at.desc())
    )
    recipes = result.scalars().all()

    return {
        'user_id':      user_id,
        'household_id': str(hh.id),
        'total':        len(recipes),
        'recipes': [
            {
                'id':           str(r.id),
                'name':         r.name,
                'servings':     r.servings,
                'ingredients':  r.ingredients,
                'cuisine':      r.cuisine,
                'pinned_for':   r.pinned_for.isoformat() if r.pinned_for else None,
                'created_at':   r.created_at.isoformat() if r.created_at else None,
            }
            for r in recipes
        ],
    }


@router.get('/')
async def recipes_index():
    """Index endpoint — lists available recipe routes."""
    return {
        'endpoints': [
            'GET /api/recipes/{user_id} — list saved recipes for a household',
        ],
        'note': 'Recipe AI generation is planned as a post-Week-3 backlog feature.',
    }
