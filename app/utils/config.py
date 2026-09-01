import os
from pathlib import Path
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    YOUTUBE_API_KEY: Optional[SecretStr] = Field(default=None, alias="YOUTUBE_API_KEY")
    INSFORGE_URL: Optional[str] = Field(default=None, alias="INSFORGE_URL")
    INSFORGE_API_KEY: Optional[SecretStr] = Field(default=None, alias="INSFORGE_API_KEY")
    INSFORGE_ANON_KEY: Optional[SecretStr] = Field(default=None, alias="INSFORGE_ANON_KEY")

    APP_NAME: str = "PRYTB-YouTubeOpportunity-HNT"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT: int = 30

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    def validate_keys(self) -> dict[str, bool]:
        """Check presence of required external API keys without exposing their values."""
        return {
            "YOUTUBE_API_KEY": bool(self.YOUTUBE_API_KEY and self.YOUTUBE_API_KEY.get_secret_value().strip()),
            "INSFORGE_URL": bool(self.INSFORGE_URL and self.INSFORGE_URL.strip()),
            "INSFORGE_API_KEY": bool(self.INSFORGE_API_KEY and self.INSFORGE_API_KEY.get_secret_value().strip()),
            "INSFORGE_ANON_KEY": bool(self.INSFORGE_ANON_KEY and self.INSFORGE_ANON_KEY.get_secret_value().strip()),
        }

settings = Settings()
