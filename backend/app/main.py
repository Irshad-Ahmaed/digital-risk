from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import AppException
from app.routers import transactions, summary, ranking

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically create tables (for demo purposes)
    from app.db.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(
    title="Digital Risk Transaction API",
    description="Backend API for processing, summarizing, and ranking transactions.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "status_code": exc.status_code
        }
    )

app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(ranking.router)

@app.get("/")
async def root():
    return {"message": "Digital Risk API is running. Check /docs for API documentation."}
