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

    POSTGRES_HOST: str = Field(default="localhost", alias="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5433, alias="POSTGRES_PORT")
    POSTGRES_DB: str = Field(default="prytb", alias="POSTGRES_DB")
    POSTGRES_USER: str = Field(default="prytb_app", alias="POSTGRES_USER")
    POSTGRES_PASSWORD: Optional[SecretStr] = Field(default=None, alias="POSTGRES_PASSWORD")

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
        """Check presence of required configuration without exposing secret values."""
        return {
            "YOUTUBE_API_KEY": bool(self.YOUTUBE_API_KEY and self.YOUTUBE_API_KEY.get_secret_value().strip()),
            "POSTGRES_HOST": bool(self.POSTGRES_HOST and self.POSTGRES_HOST.strip()),
            "POSTGRES_PORT": bool(self.POSTGRES_PORT > 0),
            "POSTGRES_DB": bool(self.POSTGRES_DB and self.POSTGRES_DB.strip()),
            "POSTGRES_USER": bool(self.POSTGRES_USER and self.POSTGRES_USER.strip()),
            "POSTGRES_PASSWORD": bool(self.POSTGRES_PASSWORD and self.POSTGRES_PASSWORD.get_secret_value().strip()),
        }

settings = Settings()
