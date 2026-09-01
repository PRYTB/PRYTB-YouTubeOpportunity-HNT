import pytest
from app.utils.config import Settings

def test_settings_default_values():
    settings = Settings(_env_file=None, YOUTUBE_API_KEY="dummy_yt", INSFORGE_URL="https://dummy.insforge.com", INSFORGE_API_KEY="dummy_api", INSFORGE_ANON_KEY="dummy_anon")
    assert settings.APP_NAME == "PRYTB-YouTubeOpportunity-HNT"
    assert settings.ENVIRONMENT == "development"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.REQUEST_TIMEOUT == 30

def test_settings_secret_masking():
    settings = Settings(_env_file=None, YOUTUBE_API_KEY="secret_key_123")
    # SecretStr string representation masks the underlying secret
    assert "secret_key_123" not in str(settings.YOUTUBE_API_KEY)
    assert settings.YOUTUBE_API_KEY.get_secret_value() == "secret_key_123"

def test_validate_keys_detection():
    settings = Settings(
        _env_file=None,
        YOUTUBE_API_KEY="fake_yt_key",
        INSFORGE_URL="https://test.insforge.com",
        INSFORGE_API_KEY="fake_api_key",
        INSFORGE_ANON_KEY=""
    )
    status = settings.validate_keys()
    assert status["YOUTUBE_API_KEY"] is True
    assert status["INSFORGE_URL"] is True
    assert status["INSFORGE_API_KEY"] is True
    assert status["INSFORGE_ANON_KEY"] is False
