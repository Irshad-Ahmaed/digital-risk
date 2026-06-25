from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.db.database import get_db
from app.schemas.schemas import SummaryResponse
from app.db.models import Transaction, User
from app.core.exceptions import UserNotFoundError

router = APIRouter(prefix="/summary", tags=["Summary"])


@router.get("/{user_id}", response_model=SummaryResponse)
async def get_user_summary(user_id: str, db: AsyncSession = Depends(get_db)):
    # ── 1. Verify user exists and grab balance ────────────────────────────────
    user_stmt = select(User.balance).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    balance = user_res.scalar_one_or_none()
    if balance is None:
        raise UserNotFoundError()

    # ── 2. Aggregate successful transactions ──────────────────────────────────
    # SQLAlchemy 2.x case() uses positional whens as tuples in a list, or keyword form.
    stmt = select(
        func.count().label("transaction_count"),
        func.coalesce(
            func.sum(case((Transaction.type == "credit", Transaction.amount), else_=0)), 0
        ).label("total_credits"),
        func.coalesce(
            func.sum(case((Transaction.type == "debit", Transaction.amount), else_=0)), 0
        ).label("total_debits"),
        func.coalesce(func.avg(Transaction.amount), 0).label("avg_transaction_amount"),
        func.min(Transaction.created_at).label("first_transaction_at"),
        func.max(Transaction.created_at).label("last_transaction_at"),
    ).where(
        Transaction.user_id == user_id,
        Transaction.status == "success",
    )

    result = await db.execute(stmt)
    agg = result.fetchone()

    # ── 3. Derive account age ─────────────────────────────────────────────────
    account_age_days = 0
    if agg.first_transaction_at and agg.last_transaction_at:
        # Both timestamps come from the DB and may be timezone-aware; use abs() for safety
        delta = agg.last_transaction_at - agg.first_transaction_at
        account_age_days = abs(delta.days) + 1

    return SummaryResponse(
        user_id=user_id,
        balance=balance,
        total_credits=int(agg.total_credits),
        total_debits=int(agg.total_debits),
        transaction_count=int(agg.transaction_count),
        avg_transaction_amount=int(agg.avg_transaction_amount),
        first_transaction_at=agg.first_transaction_at,
        last_transaction_at=agg.last_transaction_at,
        account_age_days=account_age_days,
    )
