from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from sqlalchemy.exc import IntegrityError
from typing import Optional
import uuid

from app.db.models import User, Transaction
from app.schemas.schemas import TransactionRequest, TransactionResponse
from app.core.exceptions import TransactionConflictError, InsufficientFundsError, RateLimitExceededError
from app.core.config import settings


async def check_rate_limit(db: AsyncSession, user_id: str):
    """DB-level rate limit: count transactions in the last minute for this user."""
    stmt = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.created_at >= func.now() - text("INTERVAL '1 minute'")
    )
    result = await db.execute(stmt)
    count = result.scalar_one()
    if count >= settings.RATE_LIMIT_TRANSACTIONS_PER_MINUTE:
        raise RateLimitExceededError()


async def get_existing_transaction(db: AsyncSession, transaction_id: str) -> Optional[Transaction]:
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def existing_matches_payload(existing: Transaction, request: TransactionRequest) -> bool:
    return (
        existing.user_id == request.user_id
        and existing.type == request.type
        and existing.amount == request.amount
    )


def build_already_processed_response(tx: Transaction, current_balance: int) -> TransactionResponse:
    """Return a 200 response for an idempotent retry, using the user's current balance."""
    return TransactionResponse(
        success=True,
        status="already_processed",
        transaction_id=tx.transaction_id,
        user_id=tx.user_id,
        type=tx.type,
        amount=tx.amount,
        new_balance=current_balance,
        message="Transaction already processed. Returning original result.",
    )


async def upsert_user(db: AsyncSession, user_id: str) -> User:
    """Get or create a user row, locked FOR UPDATE for concurrency safety."""
    # First try to get the existing user with a row-level lock
    stmt = select(User).where(User.id == user_id).with_for_update()
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user with zero balance
        user = User(
            id=user_id,
            username=f"user_{user_id}",
            balance=0,
        )
        db.add(user)
        await db.flush()  # write to DB so FK constraint is satisfied

    return user


async def process_transaction(db: AsyncSession, request: TransactionRequest) -> TransactionResponse:
    # ── 1. Rate-limit check (read-only, safe before any lock) ────────────────
    await check_rate_limit(db, request.user_id)

    # ── 2. Upsert user and acquire row-level lock ─────────────────────────────
    # Must happen BEFORE inserting transaction because of FK constraint.
    user = await upsert_user(db, request.user_id)

    # ── 3. Idempotency: INSERT transaction in a savepoint ─────────────────────
    # begin_nested() creates a SAVEPOINT so an IntegrityError only rolls back
    # the savepoint, not the entire outer transaction.
    tx: Optional[Transaction] = None
    try:
        async with db.begin_nested():
            tx = Transaction(
                id=str(uuid.uuid4()),
                user_id=request.user_id,
                transaction_id=request.transaction_id,
                type=request.type,
                amount=request.amount,
                status="pending",
                note=request.note,
            )
            db.add(tx)
            await db.flush()  # triggers UNIQUE constraint if duplicate
    except IntegrityError:
        # UNIQUE constraint on transaction_id fired → duplicate request
        existing = await get_existing_transaction(db, request.transaction_id)
        if existing and existing_matches_payload(existing, request):
            return build_already_processed_response(existing, user.balance)
        else:
            # Same transaction_id but different payload → conflict
            raise TransactionConflictError()

    # ── 4. Apply balance change atomically ────────────────────────────────────
    if request.type == "credit":
        balance_stmt = (
            update(User)
            .where(User.id == request.user_id)
            .values(balance=User.balance + request.amount, updated_at=func.now())
            .returning(User.balance)
        )
    else:  # debit
        # The WHERE condition `balance >= amount` acts as the atomic guard.
        balance_stmt = (
            update(User)
            .where(User.id == request.user_id, User.balance >= request.amount)
            .values(balance=User.balance - request.amount, updated_at=func.now())
            .returning(User.balance)
        )

    result = await db.execute(balance_stmt)
    new_balance = result.scalar_one_or_none()

    if new_balance is None:
        # Debit failed (insufficient funds) — mark TX as failed
        tx.status = "failed"
        await db.flush()
        raise InsufficientFundsError(user.balance, request.amount)

    # ── 5. Mark transaction successful ────────────────────────────────────────
    tx.status = "success"
    await db.flush()

    return TransactionResponse(
        success=True,
        status="processed",
        transaction_id=request.transaction_id,
        user_id=request.user_id,
        type=request.type,
        amount=request.amount,
        new_balance=new_balance,
        message="Transaction processed successfully.",
    )
