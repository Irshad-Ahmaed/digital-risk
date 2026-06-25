"""
Seed script — writes directly to the DB (bypasses rate limiting).
Run: python seed.py
"""
import asyncio
import uuid
import random

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import engine, AsyncSessionLocal, Base
from app.db.models import User, Transaction


async def upsert_user(db, user_id: str, username: str) -> User:
    stmt = pg_insert(User).values(
        id=user_id,
        username=username,
        balance=0,
    ).on_conflict_do_nothing(index_elements=["id"])
    await db.execute(stmt)
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one()


async def apply_tx(db, user: User, tx_type: str, amount: int) -> int:
    """Insert a transaction and update balance atomically. Returns new balance."""
    tx = Transaction(
        id=str(uuid.uuid4()),
        user_id=user.id,
        transaction_id=str(uuid.uuid4()),
        type=tx_type,
        amount=amount,
        status="success",
    )
    db.add(tx)
    await db.flush()

    if tx_type == "credit":
        stmt = (
            update(User)
            .where(User.id == user.id)
            .values(balance=User.balance + amount)
            .returning(User.balance)
        )
    else:
        stmt = (
            update(User)
            .where(User.id == user.id, User.balance >= amount)
            .values(balance=User.balance - amount)
            .returning(User.balance)
        )

    result = await db.execute(stmt)
    new_balance = result.scalar_one_or_none()
    if new_balance is None:
        tx.status = "failed"
        await db.flush()
        raise ValueError(f"Insufficient funds for debit of {amount}")
    return new_balance


async def seed_data():
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables verified.\n")

    scenarios = [
        {
            "user_id": "whale_alice",
            "username": "whale_alice",
            "ops": [("credit", 5_000_000)] * 3,           # 3x $50,000 — big balance
        },
        {
            "user_id": "active_bob",
            "username": "active_bob",
            "ops": [("credit", random.randint(500, 5_000)) for _ in range(25)],  # many small credits
        },
        {
            "user_id": "mixed_carol",
            "username": "mixed_carol",
            "ops": (
                [("credit", random.randint(10_000, 100_000)) for _ in range(10)] +
                [("debit", 5_000)]
            ),
        },
        {
            "user_id": "new_dave",
            "username": "new_dave",
            "ops": [("credit", 1_000)] * 2,
        },
    ]

    async with AsyncSessionLocal() as db:
        for scenario in scenarios:
            uid = scenario["user_id"]
            print(f"Seeding user: {uid}")
            async with db.begin():
                user = await upsert_user(db, uid, scenario["username"])
                for tx_type, amount in scenario["ops"]:
                    try:
                        new_bal = await apply_tx(db, user, tx_type, amount)
                        print(f"  {tx_type:6s} {amount:>10,} cents  ->  balance: {new_bal:>12,}")
                    except Exception as e:
                        print(f"  FAILED {tx_type} {amount}: {e}")
            print()

    print("Seeding complete! Check GET /ranking to see the leaderboard.")


if __name__ == "__main__":
    asyncio.run(seed_data())
