import asyncio
from app.db.database import engine, Base

async def init():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("DB Connection and Table Creation Successful!")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(init())
