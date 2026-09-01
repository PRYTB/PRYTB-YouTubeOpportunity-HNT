from unittest.mock import patch, MagicMock
import pytest
import httpx

from app.database.insforge_client import InsForgeClient, InsForgeClientError

def test_insforge_client_init():
    client = InsForgeClient(url="https://test.insforge.app", api_key="api123", anon_key="anon123")
    assert client.url == "https://test.insforge.app"
    assert client.api_key == "api123"
    assert client.anon_key == "anon123"

def test_insforge_client_missing_config():
    client = InsForgeClient(url="", api_key="", anon_key="")
    with pytest.raises(InsForgeClientError, match="INSFORGE_URL is not configured"):
        client.check_connection()

    client_no_key = InsForgeClient(url="https://test.insforge.app", api_key="", anon_key="")
    with pytest.raises(InsForgeClientError, match="Neither INSFORGE_API_KEY nor INSFORGE_ANON_KEY"):
        client_no_key.check_connection()

@patch("httpx.Client.get")
def test_insforge_check_connection_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    client = InsForgeClient(url="https://test.insforge.app", api_key="api123")
    res = client.check_connection()
    assert res["status"] == "connected"
    assert res["status_code"] == 200

@patch("httpx.Client.get")
def test_insforge_check_connection_auth_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    client = InsForgeClient(url="https://test.insforge.app", api_key="invalid_key")
    with pytest.raises(InsForgeClientError, match="InsForge authentication error"):
        client.check_connection()

@patch("httpx.Client.get")
def test_insforge_check_connection_network_error(mock_get):
    mock_get.side_effect = httpx.RequestError("Connection failed")

    client = InsForgeClient(url="https://test.insforge.app", api_key="api123")
    with pytest.raises(InsForgeClientError, match="Network error connecting to InsForge"):
        client.check_connection()
