from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://nadinet:nadinet@db:5432/nadinet"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"

    # Google AI
    GOOGLE_API_KEY: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # NLP
    FEW_SHOT_EXAMPLES_PATH: str = "./models/few_shot_examples.json"

    # Frontend
    NEXT_PUBLIC_API_URL: str = "http://localhost:3000"

    # CORS
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    # Scheduler
    SCHEDULER_TIMEZONE: str = "UTC"

    # Reporting
    NGO_NAME: str = "NadiNet NGO"

    def get_cors_origins(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return ["http://localhost:3000"]


settings = Settings()
