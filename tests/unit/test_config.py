import pytest
from app.utils.config import Settings

def test_settings_default_values():
    settings = Settings(_env_file=None, YOUTUBE_API_KEY="dummy_yt", POSTGRES_HOST="localhost", POSTGRES_PORT=5433, POSTGRES_DB="prytb", POSTGRES_USER="prytb_app")
    assert settings.APP_NAME == "PRYTB-YouTubeOpportunity-HNT"
    assert settings.ENVIRONMENT == "development"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.REQUEST_TIMEOUT == 30
    assert settings.POSTGRES_HOST == "localhost"
    assert settings.POSTGRES_PORT == 5433
    assert settings.POSTGRES_DB == "prytb"
    assert settings.POSTGRES_USER == "prytb_app"

def test_settings_secret_masking():
    settings = Settings(_env_file=None, YOUTUBE_API_KEY="secret_key_123", POSTGRES_PASSWORD="secret_pg_pass")
    assert "secret_key_123" not in str(settings.YOUTUBE_API_KEY)
    assert settings.YOUTUBE_API_KEY.get_secret_value() == "secret_key_123"
    assert "secret_pg_pass" not in str(settings.POSTGRES_PASSWORD)
    assert settings.POSTGRES_PASSWORD.get_secret_value() == "secret_pg_pass"

def test_validate_keys_detection():
    settings = Settings(
        _env_file=None,
        YOUTUBE_API_KEY="fake_yt_key",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5433,
        POSTGRES_DB="prytb",
        POSTGRES_USER="prytb_app",
        POSTGRES_PASSWORD="fake_password"
    )
    status = settings.validate_keys()
    assert status["YOUTUBE_API_KEY"] is True
    assert status["POSTGRES_HOST"] is True
    assert status["POSTGRES_PORT"] is True
    assert status["POSTGRES_DB"] is True
    assert status["POSTGRES_USER"] is True
    assert status["POSTGRES_PASSWORD"] is True
