from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/digital_risk"
    MAX_AMOUNT_PER_TRANSACTION: int = 100000000
    MIN_AMOUNT_PER_TRANSACTION: int = 1
    INITIAL_BALANCE: int = 0
    RATE_LIMIT_TRANSACTIONS_PER_MINUTE: int = 10
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:8000"]
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
