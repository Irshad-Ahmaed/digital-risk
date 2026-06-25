import asyncio
from app.db.database import engine, AsyncSessionLocal
from app.services.transaction_service import process_transaction
from app.schemas.schemas import TransactionRequest

async def test():
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                req = TransactionRequest(
                    user_id="test2",
                    transaction_id="123e4567-e89b-12d3-a456-426614174001",
                    type="credit",
                    amount=100
                )
                res = await process_transaction(db, req)
                print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
