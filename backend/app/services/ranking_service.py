from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta
import math

from app.db.models import User, Transaction
from app.schemas.schemas import UserRanking, RankingResponse


async def compute_rankings(db: AsyncSession) -> RankingResponse:
    now = datetime.now(timezone.utc)

    # ── 1. Aggregate per-user stats (only successful transactions) ────────────
    stmt = select(
        User.id.label("user_id"),
        User.username,
        User.balance,
        func.count(Transaction.id).label("tx_count"),
        func.min(Transaction.created_at).label("first_tx"),
        func.max(Transaction.created_at).label("last_tx"),
    ).outerjoin(
        Transaction,
        (Transaction.user_id == User.id) & (Transaction.status == "success"),
    ).group_by(User.id, User.username, User.balance)

    result = await db.execute(stmt)
    users_data = result.all()

    if not users_data:
        return RankingResponse(generated_at=now, total_users=0, ranking=[])

    # ── 2. Pull abuse map (failed / rejected tx counts per user) ─────────────
    abuse_stmt = select(
        Transaction.user_id,
        func.count(Transaction.id).label("failed_count"),
    ).where(Transaction.status.in_(["failed", "rejected"])).group_by(Transaction.user_id)

    abuse_res = await db.execute(abuse_stmt)
    abuse_map: dict[str, int] = {row.user_id: row.failed_count for row in abuse_res.all()}

    # ── 3. Compute normalization maximums ─────────────────────────────────────
    max_balance = max((u.balance for u in users_data), default=0)

    def _active_days(u) -> int:
        if u.first_tx and u.last_tx:
            # Timestamps are timezone-aware from Neon; subtraction is safe
            delta: timedelta = u.last_tx - u.first_tx
            return abs(delta.days) + 1
        return 0

    max_days = max((_active_days(u) for u in users_data), default=0)

    # ── 4. Score each user ────────────────────────────────────────────────────
    ranked: list[dict] = []
    for u in users_data:
        # Balance score: normalised 0-1 relative to top balance holder
        balance_score = (u.balance / max_balance) if max_balance > 0 else 0.0

        # Activity score: log-scale capped at log(51) to prevent spam gaming
        # log(1)=0 when tx_count=0, log(51)/log(51)=1 at cap
        CAP = 51
        activity_score = (
            min(math.log(u.tx_count + 1) / math.log(CAP), 1.0)
            if u.tx_count > 0
            else 0.0
        )

        # Longevity score: log-scale active days
        active_days = _active_days(u)
        longevity_score = (
            min(math.log(active_days + 1) / math.log(max_days + 1), 1.0)
            if max_days > 0
            else 0.0
        )

        # Abuse penalty: capped at 1.0 (10 failed txs = full penalty)
        failed_tx = abuse_map.get(u.user_id, 0)
        abuse_penalty = min(failed_tx / 10.0, 1.0)

        final_score = (
            balance_score * 0.50
            + activity_score * 0.20
            + longevity_score * 0.20
            - abuse_penalty * 0.10
        )
        final_score = round(max(final_score, 0.0), 4)

        ranked.append({
            "user_id": u.user_id,
            "username": u.username,
            "score": final_score,
            "balance": u.balance,
            "transaction_count": u.tx_count,
            "active_days": active_days,
            "score_breakdown": {
                "balance_score": round(balance_score, 4),
                "activity_score": round(activity_score, 4),
                "longevity_score": round(longevity_score, 4),
                "abuse_penalty": round(abuse_penalty, 4),
            },
        })

    # ── 5. Sort and assign ranks ──────────────────────────────────────────────
    # Primary: score desc; secondary tiebreak: balance desc
    ranked.sort(key=lambda x: (x["score"], x["balance"]), reverse=True)

    user_rankings = []
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
        user_rankings.append(UserRanking(**r))

    return RankingResponse(
        generated_at=now,
        total_users=len(user_rankings),
        ranking=user_rankings,
    )
