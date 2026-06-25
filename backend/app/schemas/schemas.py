from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime
import uuid


class TransactionRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    transaction_id: str = Field(..., min_length=1, max_length=100)
    type: Literal["credit", "debit"]
    amount: int = Field(..., gt=0, le=100_000_000)  # stored in cents; max $1,000,000
    note: Optional[str] = Field(None, max_length=255)

    @field_validator("transaction_id")
    def validate_uuid_format(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("transaction_id must be a valid UUID")
        return v


class TransactionResponse(BaseModel):
    success: bool
    status: str                       # "processed" | "already_processed"
    transaction_id: str
    user_id: str
    type: Optional[str] = None
    amount: Optional[int] = None
    new_balance: Optional[int] = None  # canonical balance field used everywhere
    message: str


class SummaryResponse(BaseModel):
    user_id: str
    balance: int
    total_credits: int
    total_debits: int
    transaction_count: int
    avg_transaction_amount: int
    first_transaction_at: Optional[datetime] = None
    last_transaction_at: Optional[datetime] = None
    account_age_days: int


class UserRanking(BaseModel):
    rank: int
    user_id: str
    username: str
    score: float
    balance: int
    transaction_count: int
    active_days: int
    score_breakdown: dict


class RankingResponse(BaseModel):
    generated_at: datetime
    total_users: int
    ranking: list[UserRanking]
