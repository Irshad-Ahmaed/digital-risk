from sqlalchemy import Column, String, BigInteger, DateTime, CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    transactions = relationship("Transaction", back_populates="user")
    
    __table_args__ = (
        CheckConstraint('balance >= 0', name='check_balance_non_negative'),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    transaction_id = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    amount = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False, default="success")
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User", back_populates="transactions")
    
    __table_args__ = (
        CheckConstraint("type IN ('credit', 'debit')", name='check_transaction_type'),
        CheckConstraint('amount > 0', name='check_amount_positive'),
        CheckConstraint("status IN ('success', 'failed', 'pending', 'rejected', 'already_processed')", name='check_status_valid'),
        Index('idx_transactions_user_time', 'user_id', 'created_at'),
    )
