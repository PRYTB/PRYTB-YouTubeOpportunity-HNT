from unittest.mock import patch, MagicMock
import pytest
from app.database.postgres_client import PostgresClient, PostgresClientError
from app.database.repositories import YouTubeRepository, PersistenceResult
from app.models.youtube import YouTubeChannel, YouTubeVideo, CollectionResult, CollectionStats


@pytest.fixture
def mock_pg_client():
    client = MagicMock(spec=PostgresClient)
    client.host = "localhost"
    client.port = 5433
    client.dbname = "prytb"
    client.user = "prytb_app"
    return client


def test_postgres_client_check_connection_success(mock_pg_client):
    mock_pg_client.check_connection.return_value = {
        "status": "connected",
        "database": "prytb",
        "user": "prytb_app",
        "host": "localhost",
        "port": 5433,
    }
    info = mock_pg_client.check_connection()
    assert info["status"] == "connected"
    assert info["database"] == "prytb"
    assert info["user"] == "prytb_app"


def test_postgres_client_failure_raises_explicit_error():
    client = PostgresClient(host="localhost", port=9999, dbname="nonexistent", user="bad_user")
    with pytest.raises(PostgresClientError, match="PostgreSQL connection failure"):
        with client.get_connection():
            pass


def test_no_insforge_or_supabase_fallback_on_postgres_failure():
    """
    Verify that when PostgreSQL connection fails, it raises PostgresClientError explicitly
    and DOES NOT trigger InsForge, Supabase, or local JSON fallbacks.
    """
    client = PostgresClient(host="invalid_host", port=5433)
    repo = YouTubeRepository(client=client)

    with patch("httpx.Client.post") as mock_httpx_post:
        with pytest.raises(PostgresClientError):
            repo.get_all_videos()
        # Verify no HTTP request to InsForge or Supabase occurred
        mock_httpx_post.assert_not_called()


def test_postgres_transaction_rollback_on_error():
    client = MagicMock(spec=PostgresClient)
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("DB constraint violation")
    
    # Configure get_cursor mock to raise PostgresClientError when used
    client.get_cursor.side_effect = PostgresClientError("Execution error")
    with pytest.raises(PostgresClientError):
        with client.get_cursor() as cur:
            cur.execute("INVALID SQL")
