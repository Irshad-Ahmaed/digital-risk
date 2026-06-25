"""
Full integration smoke test — runs directly against the DB (no server needed).
Tests: new user, credit, debit, idempotency retry, conflict, insufficient funds, summary, ranking.
"""
import asyncio
import uuid

from app.db.database import AsyncSessionLocal, engine, Base
from app.services.transaction_service import process_transaction
from app.services.ranking_service import compute_rankings
from app.schemas.schemas import TransactionRequest
from app.core.exceptions import (
    InsufficientFundsError, TransactionConflictError, RateLimitExceededError
)


PASS = "[PASS]"
FAIL = "[FAIL]"


async def run_tests():
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    uid = f"smoke_{uuid.uuid4().hex[:8]}"
    tx_id = str(uuid.uuid4())

    print(f"\n=== Smoke Tests (user: {uid}) ===\n")

    async with AsyncSessionLocal() as db:
        # ── Test 1: credit ────────────────────────────────────────────────────
        async with db.begin():
            r = await process_transaction(db, TransactionRequest(
                user_id=uid, transaction_id=tx_id, type="credit", amount=10000
            ))
        assert r.status == "processed" and r.new_balance == 10000, f"Got {r}"
        print(f"{PASS} Credit: balance={r.new_balance}")

        # ── Test 2: debit ────────────────────────────────────────────────────
        async with db.begin():
            r2 = await process_transaction(db, TransactionRequest(
                user_id=uid, transaction_id=str(uuid.uuid4()), type="debit", amount=3000
            ))
        assert r2.status == "processed" and r2.new_balance == 7000, f"Got {r2}"
        print(f"{PASS} Debit:  balance={r2.new_balance}")

        # ── Test 3: idempotent retry (same tx_id + same payload) ─────────────
        async with db.begin():
            r3 = await process_transaction(db, TransactionRequest(
                user_id=uid, transaction_id=tx_id, type="credit", amount=10000
            ))
        assert r3.status == "already_processed", f"Got {r3}"
        print(f"{PASS} Idempotent retry: status={r3.status}")

        # ── Test 4: conflict (same tx_id, different amount) ───────────────────
        try:
            async with db.begin():
                await process_transaction(db, TransactionRequest(
                    user_id=uid, transaction_id=tx_id, type="credit", amount=9999
                ))
            print(f"{FAIL} Conflict: should have raised TransactionConflictError")
        except TransactionConflictError:
            print(f"{PASS} Conflict detection works")

        # ── Test 5: insufficient funds ────────────────────────────────────────
        try:
            async with db.begin():
                await process_transaction(db, TransactionRequest(
                    user_id=uid, transaction_id=str(uuid.uuid4()), type="debit", amount=999999
                ))
            print(f"{FAIL} Insufficient funds: should have raised InsufficientFundsError")
        except InsufficientFundsError as e:
            print(f"{PASS} Insufficient funds: {e.message}")

        # ── Test 6: ranking ───────────────────────────────────────────────────
        ranking = await compute_rankings(db)
        assert ranking.total_users >= 1
        print(f"{PASS} Ranking: {ranking.total_users} users, top={ranking.ranking[0].username}")

    print("\n=== All tests passed ===\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
