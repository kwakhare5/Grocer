import asyncio
from sqlalchemy import text
from backend.database.connection import engine, init_db

async def main():
    await init_db()
    print("Base tables created.")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("SELECT create_hypertable('price_history', 'recorded_at', if_not_exists => TRUE);"))
            print("Hypertable created successfully.")
        except Exception as e:
            print(f"Error creating hypertable: {e}")

if __name__ == "__main__":
    asyncio.run(main())
