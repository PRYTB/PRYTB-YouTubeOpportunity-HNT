import pytest
from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.utils.config import settings

@pytest.mark.integration
def test_insforge_connection():
    if not settings.INSFORGE_URL or not settings.INSFORGE_URL.strip():
        pytest.skip("INSFORGE_URL not configured in .env; skipping live integration test.")

    client = InsForgeClient()
    try:
        res = client.check_connection()
        assert res.get("status") == "connected"
    except InsForgeClientError as exc:
        pytest.fail(f"InsForge connection failed: {exc}")
