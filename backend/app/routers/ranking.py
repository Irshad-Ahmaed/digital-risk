from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.schemas import RankingResponse
from app.services.ranking_service import compute_rankings

router = APIRouter(prefix="/ranking", tags=["Ranking"])

@router.get("", response_model=RankingResponse)
async def get_rankings(db: AsyncSession = Depends(get_db)):
    return await compute_rankings(db)
