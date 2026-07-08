from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime, timezone
from typing import Any

from backend.database.connection import get_db, get_checkpointer
from backend.database.models import Household, RestockAlert
from backend.agents.restock_agent import build_restock_graph
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# Persistent in-memory checkpointer for local development / Windows compatibility fallback
memory_checkpointer = MemorySaver()

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    content_type = request.headers.get("content-type", "")
    is_json = "application/json" in content_type

    # Secure webhook verification (Twilio signature check)
    from backend.config import settings
    if settings.is_twilio_configured() and not is_json and settings.ENVIRONMENT != "development":
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            logger.warning("Rejecting request: Missing X-Twilio-Signature header.")
            return Response(content="Unauthorized: Missing signature", status_code=401)
        
        # Reconstruct public URL when behind reverse proxies
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.netloc)
        path = request.url.path
        query = request.url.query
        url = f"{proto}://{host}{path}"
        if query:
            url += f"?{query}"
            
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        
        # Twilio request signature verification needs form data parameters
        params = {}
        if not is_json:
            try:
                form_data = await request.form()
                params = {k: v for k, v in form_data.items()}
            except Exception as form_err:
                logger.error(f"Error parsing form data for signature validation: {form_err}")
                
        if not validator.validate(url, params, signature):
            logger.warning(f"Rejecting request: Invalid X-Twilio-Signature. Reconstructed URL: {url}")
            return Response(content="Unauthorized: Invalid signature", status_code=401)

    phone = ""
    message = ""

    try:
        if is_json:
            payload = await request.json()
            phone = str(payload.get("phone", "")).replace("whatsapp:", "")
            message = str(payload.get("message", ""))
        else:
            form_data = await request.form()
            phone = str(form_data.get("From") or "").replace("whatsapp:", "")
            message = str(form_data.get("Body") or "")
    except Exception as e:
        logger.error(f"Error parsing request payload: {e}")
        reply = "Invalid request format."
        if is_json:
            return {"response_message": reply}
        else:
            return Response(content=f"<Response><Message>{reply}</Message></Response>", media_type="application/xml")

    # Step 1: Look up household by phone number
    hh = None
    try:
        stmt = select(Household).where(Household.phone_number == phone)
        res = await db.execute(stmt)
        hh = res.scalar_one_or_none()

        # Fallback for sandbox demo: if not found, map to the first household in DB (e.g. demo_user_001)
        if not hh:
            stmt_fallback = select(Household).order_by(Household.created_at.asc())
            res_fallback = await db.execute(stmt_fallback)
            hh = res_fallback.scalars().first()
            if hh:
                # Link this phone number to the demo household for convenience
                hh.phone_number = phone  # type: ignore
                await db.commit()
                logger.info(f"Auto-mapped phone {phone} to demo household {hh.user_id}")
    except Exception as e:
        logger.error(f"Database error during household lookup: {e}")
        # If DB is offline, we fallback to a mock/dry-run response for unit tests
        reply = f"System Offline. Simulated response: Received '{message}'"
        if is_json:
            return {"response_message": reply}
        else:
            return Response(content=f"<Response><Message>{reply}</Message></Response>", media_type="application/xml")

    if not hh:
        reply = "Welcome! No active household was found in the database. Please generate seed orders first."
        if is_json:
            return {"response_message": reply}
        else:
            return Response(content=f"<Response><Message>{reply}</Message></Response>", media_type="application/xml")

    if message.strip().lower() == "check":
        try:
            from backend.api.routes.restock import check_depletions_for_household
            from backend.seed.catalog import CATALOG

            # Query existing pre-computed model predictions directly from DB to prevent drift
            logger.info(f"Querying pre-computed model predictions for household {hh.id} (user {hh.user_id}) during 'check'")
            items = await check_depletions_for_household(str(hh.id), db, bypass_cooldown=True)
            
            if items:
                from backend.seed.catalog import format_restock_alert_message
                alert_msg = format_restock_alert_message(items)
                alert = RestockAlert(
                    household_id=hh.id,
                    item_ids=[item['item_id'] for item in items],
                    message_sent=alert_msg,
                    sent_at=datetime.now(timezone.utc),
                    status="sent",
                )
                db.add(alert)
                await db.commit()
                
                # Reset the agent's checkpointer thread state for this new alert list
                config: Any = {"configurable": {"thread_id": phone}}
                new_depleting = [
                    {
                        "item_name": item["item_name"],
                        "confidence_score": item["confidence_score"],
                        "days_remaining": item["days_remaining"]
                    }
                    for item in items
                ]
                
                # Reset memory checkpointer
                try:
                    agent = build_restock_graph().compile(checkpointer=memory_checkpointer)
                    await agent.aupdate_state(config, {
                        "household_id": str(hh.id),
                        "depleting_items": new_depleting,
                        "stage": "awaiting_reply",
                        "confirmed_items": [],
                        "confirmed_quantities": {},
                        "cart_id": None,
                        "cart_total": None,
                        "order_id": None,
                        "response_message": alert_msg,
                        "error": None
                    })
                except Exception as e:
                    logger.error(f"Error resetting memory checkpointer: {e}")
                
                # Reset DB checkpointer
                try:
                    async with await get_checkpointer() as cp:
                        agent = build_restock_graph().compile(checkpointer=cp)
                        await agent.aupdate_state(config, {
                            "household_id": str(hh.id),
                            "depleting_items": new_depleting,
                            "stage": "awaiting_reply",
                            "confirmed_items": [],
                            "confirmed_quantities": {},
                            "cart_id": None,
                            "cart_total": None,
                            "order_id": None,
                            "response_message": alert_msg,
                            "error": None
                        })
                except Exception as e:
                    logger.error(f"Error resetting DB checkpointer: {e}")
                
                reply_msg = alert_msg
            else:
                reply_msg = "All set! No items are currently running low in your household. 👍"
                # Reset agent state to "done"
                config: Any = {"configurable": {"thread_id": phone}}
                try:
                    agent = build_restock_graph().compile(checkpointer=memory_checkpointer)
                    await agent.aupdate_state(config, {
                        "household_id": str(hh.id),
                        "depleting_items": [],
                        "stage": "done",
                        "confirmed_items": [],
                        "cart_id": None,
                        "cart_total": None,
                        "order_id": None,
                        "response_message": reply_msg,
                        "error": None
                    })
                except Exception as e:
                    logger.error(f"Error resetting memory checkpointer to done: {e}")
                try:
                    async with await get_checkpointer() as cp:
                        agent = build_restock_graph().compile(checkpointer=cp)
                        await agent.aupdate_state(config, {
                            "household_id": str(hh.id),
                            "depleting_items": [],
                            "stage": "done",
                            "confirmed_items": [],
                            "cart_id": None,
                            "cart_total": None,
                            "order_id": None,
                            "response_message": reply_msg,
                            "error": None
                        })
                except Exception as e:
                    logger.error(f"Error resetting DB checkpointer to done: {e}")
                
                reply_msg = reply_msg
        except Exception as e:
            logger.error(f"Error in manual check: {e}")
            reply_msg = "Sorry, I couldn't run a depletion check right now. Please try again later."
            
        if is_json:
            return {"response_message": reply_msg}
        else:
            return Response(content=f"<Response><Message>{reply_msg}</Message></Response>", media_type="application/xml")

    # Step 3: Get active depleting items for this household from the latest alert
    depleting_items = []
    alert = None
    is_new_alert = False
    try:
        stmt_alert = select(RestockAlert).where(RestockAlert.household_id == hh.id).order_by(RestockAlert.sent_at.desc())
        res_alert = await db.execute(stmt_alert)
        alert = res_alert.scalars().first()
        
        if alert is not None and alert.item_ids is not None:
            if alert.status == "pending":  # type: ignore
                is_new_alert = True
                alert.status = "sent"  # type: ignore
                await db.commit()
                logger.info(f"New alert detected for household {hh.user_id}, status updated to 'sent'.")
            
            # Map item IDs to human-readable names from our catalog and lookup actual predictions
            from backend.seed.catalog import CATALOG
            from backend.database.models import ConsumptionModel
            
            # Query the database for the actual consumption models for these items
            alert_item_ids: list[str] = alert.item_ids  # type: ignore
            stmt_models = select(ConsumptionModel).where(
                ConsumptionModel.household_id == hh.id,
                ConsumptionModel.item_id.in_(alert_item_ids)
            )
            res_models = await db.execute(stmt_models)
            models_list = res_models.scalars().all()
            models_by_item = {str(m.item_id): m for m in models_list}

            depleting_items = []
            for item_id in alert_item_ids:
                model = models_by_item.get(item_id)
                days_remaining = 1.0
                confidence_score = 0.8
                if model:
                    confidence_score = model.confidence_score if model.confidence_score is not None else 0.8
                    if model.estimated_depletion_date is not None:
                        dep_date = model.estimated_depletion_date
                        if dep_date.tzinfo is None:
                            dep_date = dep_date.replace(tzinfo=timezone.utc)
                        days_remaining = (dep_date - datetime.now(timezone.utc)).total_seconds() / 86400

                cat_item = next((item for item in CATALOG if item["id"] == item_id), None)
                item_name = cat_item["name"] if cat_item else item_id

                depleting_items.append({
                    "item_name": item_name,
                    "confidence_score": confidence_score,
                    "days_remaining": round(days_remaining, 1)
                })
    except Exception as e:
        logger.warning(f"Error fetching active alert details: {e}")

    # Fallback to database active depletions or catalog defaults if no active alert items exist
    if not depleting_items:
        try:
            from backend.api.routes.restock import check_depletions_for_household
            db_depletions = await check_depletions_for_household(str(hh.id), db, bypass_cooldown=True)
            if db_depletions:
                depleting_items = [
                    {
                        "item_name": item["item_name"],
                        "confidence_score": item["confidence_score"],
                        "days_remaining": item["days_remaining"]
                    }
                    for item in db_depletions
                ]
                logger.info(f"Chatbot auto-synced with {len(depleting_items)} active depletions from DB.")
        except Exception as e:
            logger.warning(f"Failed to fetch on-the-fly depletions for chatbot: {e}")
            
    if not depleting_items:
        depleting_items = [{"item_name": "Fortune Sunflower Oil 1L", "confidence_score": 0.9, "days_remaining": 1.0}]

    # Step 4: Run the stateful LangGraph agent
    config: Any = {"configurable": {"thread_id": phone}}
    reply_msg = ""
    final_stage = None
    order_id = None

    try:
        async with await get_checkpointer() as cp:
            agent = build_restock_graph().compile(checkpointer=cp)
            existing_state = await agent.aget_state(config)
            
            should_reset = is_new_alert or not existing_state or not existing_state.values
            
            if should_reset:
                initial_values = {
                    "household_id": str(hh.id),
                    "depleting_items": depleting_items,
                    "stage": "awaiting_reply" if is_new_alert else "awaiting_order",
                    "confirmed_items": [],
                    "confirmed_quantities": {},
                    "cart_id": None,
                    "cart_total": None,
                    "order_id": None,
                    "response_message": "",
                    "error": None
                }
                await agent.aupdate_state(config, initial_values)
                logger.info(f"Reset LangGraph checkpointer state for thread {phone}")
                
            payload = {"user_message": message}
            result = await agent.ainvoke(payload, config=config)
            reply_msg = result.get("response_message", "")
            
            final_state = await agent.aget_state(config)
            if final_state and final_state.values:
                final_stage = final_state.values.get("stage")
                order_id = final_state.values.get("order_id")
    except Exception as e:
        logger.error(f"Error running LangGraph agent: {e}")
        # Local fallback execution with MemorySaver if DB/checkpointer is offline or failed
        try:
            agent = build_restock_graph().compile(checkpointer=memory_checkpointer)
            existing_state = agent.get_state(config)
            
            should_reset = is_new_alert or not existing_state or not existing_state.values
            
            if should_reset:
                initial_values = {
                    "household_id": str(hh.id),
                    "depleting_items": depleting_items,
                    "stage": "awaiting_reply" if is_new_alert else "awaiting_order",
                    "confirmed_items": [],
                    "confirmed_quantities": {},
                    "cart_id": None,
                    "cart_total": None,
                    "order_id": None,
                    "response_message": "",
                    "error": None
                }
                await agent.aupdate_state(config, initial_values)  # type: ignore
                logger.info(f"Reset LangGraph memory state for thread {phone}")
                
            payload = {"user_message": message}
            result = await agent.ainvoke(payload, config=config)
            reply_msg = result.get("response_message", "")
            
            final_state = agent.get_state(config)
            if final_state and final_state.values:
                final_stage = final_state.values.get("stage")
                order_id = final_state.values.get("order_id")
        except Exception as inner_e:
            logger.error(f"Double agent failure: {inner_e}")
            reply_msg = f"Sorry, the assistant is currently unavailable. (Offline fallback: received '{message}')"

    # Step 5: Update alert status in DB
    if alert:
        try:
            if final_stage == "done":
                if order_id:
                    alert.status = "acted"  # type: ignore
                    alert.order_id_placed = order_id
                    alert.acted_at = datetime.now(timezone.utc)  # type: ignore
                    
                    # Sync the order from the mock server to the database and rebuild models
                    try:
                        from backend.services.sync_service import fetch_and_sync_orders
                        from backend.ml.consumption_model import ConsumptionModeler
                        from backend.ml.household_profiler import update_household_profile
                        
                        logger.info(f"Syncing orders after successful chatbot checkout for household {hh.user_id}")
                        await fetch_and_sync_orders(str(hh.id), str(hh.user_id), db)
                        
                        logger.info(f"Rebuilding ML consumption models for household {hh.user_id}")
                        modeler = ConsumptionModeler()
                        await modeler.rebuild_all_models(str(hh.id), db)
                        await update_household_profile(str(hh.id), db)
                        logger.info(f"ML models successfully rebuilt for household {hh.user_id}")
                    except Exception as sync_err:
                        logger.error(f"Failed to sync orders/rebuild models in webhook: {sync_err}")
                else:
                    alert.status = "dismissed"  # type: ignore
                    alert.acted_at = datetime.now(timezone.utc)  # type: ignore
            elif final_stage:
                alert.status = "sent"  # type: ignore
            
            await db.commit()
            logger.info(f"Updated DB alert status to '{alert.status}' for household {hh.user_id}")
        except Exception as e:
            logger.error(f"Failed to update alert status in DB: {e}")

    # Step 6: Return response in requested format
    if is_json:
        return {"response_message": reply_msg}
    else:
        return Response(content=f"<Response><Message>{reply_msg}</Message></Response>", media_type="application/xml")


async def send_whatsapp_message(to_phone: str, body: str) -> bool:
    """
    Sends a WhatsApp message using Twilio API.
    Falls back to logging if Twilio credentials are not set.
    """
    from backend.config import settings
    import asyncio
    
    # Clean up phone format (ensure it starts with whatsapp:)
    to_whatsapp = to_phone
    if not to_whatsapp.startswith("whatsapp:"):
        to_whatsapp = f"whatsapp:{to_phone}"
        
    logger.info(f"[WhatsApp] Attempting to send message to {to_whatsapp}: {body}")
    
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("[WhatsApp] Twilio credentials not set. Message logged but not sent via Twilio.")
        return True
        
    def _send():
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            body=body,
            to=to_whatsapp
        )

    try:
        await asyncio.to_thread(_send)
        logger.info(f"[WhatsApp] Message successfully dispatched to {to_whatsapp}")
        return True
    except Exception as e:
        logger.error(f"[WhatsApp] Failed to send message via Twilio: {e}")
        return False
