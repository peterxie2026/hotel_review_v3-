from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "酒店OTA点评回复系统"
    VERSION: str = "3.0.0"

    DATABASE_URL: str = "sqlite:///./hotel_review.db"
    REDIS_URL: str = ""

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    ENCRYPTION_KEY: str = "change-me-encryption-key-32bytes!!"  # Fernet key base

    AI_API_KEY: str = ""
    AI_PROVIDER: str = "deepseek"
    AI_MODEL: str = "deepseek-chat"

    BROWSER_HEADLESS: bool = True
    BROWSER_POOL_SIZE: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
