import asyncio
from app.db.database import engine, Base
from app.routers.summary import get_user_summary
from app.services.transaction_service import process_transaction
from app.services.ranking_service import compute_rankings
from app.schemas.schemas import TransactionRequest

print("Modules loaded successfully!")
