import logging
from datetime import datetime, timedelta
import pandas as pd
from prophet import Prophet
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Order, OrderItem, ConsumptionModel
from backend.config import settings
from backend.ml.confidence_scorer import ConfidenceScorer

logger = logging.getLogger(__name__)

class ConsumptionModeler:
    MIN_DATA_POINTS = 3

    async def build_model_for_item(self, household_id: str, item_id: str, item_name: str, db: AsyncSession) -> dict | None:
        # Fetch purchase history for this item
        stmt = (
            select(OrderItem.standard_quantity, Order.placed_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .where(OrderItem.item_id == item_id)
            .order_by(Order.placed_at.asc())
        )
        result = await db.execute(stmt)
        purchases = result.mappings().all()

        if len(purchases) < self.MIN_DATA_POINTS:
            return None

        # Prepare DataFrame for Prophet
        # Prophet expects columns 'ds' (datestamp) and 'y' (value)
        df = pd.DataFrame({
            "ds": pd.to_datetime([p["placed_at"] for p in purchases]).tz_localize(None),
            "y":  [p["standard_quantity"] for p in purchases]
        })

        try:
            import logging as log
            log.getLogger('prophet').setLevel(log.WARNING)
            log.getLogger('cmdstanpy').setLevel(log.WARNING)
            
            model = Prophet(
                seasonality_mode='multiplicative',
                yearly_seasonality=False,
                weekly_seasonality=(len(purchases) >= 10),
                daily_seasonality=False,
                interval_width=0.80
            )
            model.fit(df)
        except Exception as e:
            logger.error(f"Prophet failed for {item_name}: {e}")
            return None

        total_qty = df["y"].sum()
        days_elapsed = max((df["ds"].max() - df["ds"].min()).days, 1)
        avg_daily = float(total_qty / days_elapsed)

        # Calculate average cycle days
        time_diffs = df["ds"].diff().dt.days.dropna()
        cycle_days = float(time_diffs.mean()) if not time_diffs.empty else 0.0

        last = purchases[-1]
        last_date = last["placed_at"]
        last_qty  = float(last["standard_quantity"])
        
        # Calculate estimated depletion date
        if avg_daily > 0:
            depletion = last_date + timedelta(days=last_qty / avg_daily)
        else:
            depletion = None

        # Confidence Score — delegate to ConfidenceScorer (single source of truth)
        # Why: avoids duplicating the formula here and in confidence_scorer.py
        scorer = ConfidenceScorer()
        purchase_dates = [p["placed_at"] for p in purchases]
        confidence = scorer.score(purchase_dates, len(purchases))

        if confidence < settings.MIN_CONFIDENCE:
            return None

        return {
            "household_id": household_id, 
            "item_id": item_id, 
            "item_name": item_name,
            "avg_daily_consumption": round(avg_daily, 4),
            "consumption_cycle_days": round(cycle_days, 1),
            "last_purchase_date": last_date, 
            "last_purchase_quantity": last_qty,
            "estimated_depletion_date": depletion,
            "confidence_score": round(confidence, 3),
            "data_points": len(purchases), 
            "updated_at": datetime.now()
        }

    async def rebuild_all_models(self, household_id: str, db: AsyncSession) -> dict:
        # Find distinct items purchased at least MIN_DATA_POINTS times
        stmt = (
            select(OrderItem.item_id, OrderItem.item_name, func.count().label('cnt'))
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.household_id == household_id)
            .group_by(OrderItem.item_id, OrderItem.item_name)
            .having(func.count() >= self.MIN_DATA_POINTS)
            .order_by(func.count().desc())
        )
        result = await db.execute(stmt)
        items = result.mappings().all()

        results = {"built": 0, "skipped": 0, "errors": 0}
        
        for item in items:
            try:
                data = await self.build_model_for_item(
                    household_id, item["item_id"], item["item_name"], db
                )
                if data:
                    # Upsert into consumption_models table
                    stmt = select(ConsumptionModel).where(
                        ConsumptionModel.household_id == household_id,
                        ConsumptionModel.item_id == item["item_id"]
                    )
                    existing_result = await db.execute(stmt)
                    existing_model = existing_result.scalar_one_or_none()
                    
                    if existing_model:
                        for key, value in data.items():
                            setattr(existing_model, key, value)
                    else:
                        new_model = ConsumptionModel(**data)
                        db.add(new_model)
                        
                    results["built"] += 1
                else:
                    results["skipped"] += 1
            except Exception as e:
                logger.error(f"Error building model for {item['item_name']}: {e}")
                await db.rollback()
                results["errors"] += 1
                
        await db.commit()
        return results
