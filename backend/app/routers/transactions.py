from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.schemas import TransactionRequest, TransactionResponse
from app.services.transaction_service import process_transaction

router = APIRouter(prefix="/transaction", tags=["Transaction"])


@router.post("", response_model=TransactionResponse, status_code=200)
async def create_transaction(
    request: TransactionRequest,
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        return await process_transaction(db, request)
