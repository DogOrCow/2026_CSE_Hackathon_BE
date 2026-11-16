from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

KST = ZoneInfo("Asia/Seoul")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./dev.db"
    JWT_SECRET: str = "dev-secret"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    JUDGE_API_KEY: str = ""
    JUDGE_THRESHOLD: float = 0.6
    JUDGE_MODEL: str = ""
    CORS_ORIGINS: str = ""
    TZ: str = "Asia/Seoul"
    SEMESTER_START: date = date(2026, 9, 1)
    ENV: str = "dev"
    DEMO_ALWAYS_LIVE: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.ENV == "dev"


settings = Settings()


def now_kst() -> datetime:
    """서버 TZ 설정과 무관하게 항상 Asia/Seoul 기준 현재 시각."""
    return datetime.now(KST)
