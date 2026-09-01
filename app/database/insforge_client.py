from typing import Any, Dict, Optional
import httpx

from app.utils.config import settings
from app.utils.logger import logger

class InsForgeClientError(Exception):
    """Base exception for InsForge client errors."""
    pass

class InsForgeClient:
    """
    Reusable access client for InsForge backend API.
    Uses INSFORGE_API_KEY (service/backend role key) for administrative backend calls,
    or INSFORGE_ANON_KEY for public/anonymous operations if needed.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        anon_key: Optional[str] = None,
        timeout: int = settings.REQUEST_TIMEOUT
    ):
        if url is not None:
            self.url = url.rstrip("/")
        else:
            self.url = (settings.INSFORGE_URL or "").rstrip("/")
        
        if api_key is not None:
            key = api_key
        else:
            key = settings.INSFORGE_API_KEY.get_secret_value() if settings.INSFORGE_API_KEY else ""
        self.api_key = key.strip()
        
        if anon_key is not None:
            a_key = anon_key
        else:
            a_key = settings.INSFORGE_ANON_KEY.get_secret_value() if settings.INSFORGE_ANON_KEY else ""
        self.anon_key = a_key.strip()
        
        self.timeout = timeout

    def _get_headers(self, use_anon: bool = False) -> Dict[str, str]:
        key = self.anon_key if use_anon else self.api_key
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if key:
            headers["Authorization"] = f"Bearer {key}"
            headers["apikey"] = key
        return headers

    def check_connection(self) -> Dict[str, Any]:
        """
        Perform a safe, non-destructive read operation to verify InsForge connectivity.
        """
        if not self.url:
            raise InsForgeClientError("INSFORGE_URL is not configured.")
        if not self.api_key and not self.anon_key:
            raise InsForgeClientError("Neither INSFORGE_API_KEY nor INSFORGE_ANON_KEY is configured.")

        # Non-destructive health/ping endpoint or API root check
        health_url = f"{self.url}/rest/v1/"
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(health_url, headers=self._get_headers())
                
                # Check status code (200, 204, or standard REST root response)
                if response.status_code in [200, 204, 404]:
                    # Even a 404 on API root indicates reachability of the HTTP service
                    return {
                        "status": "connected",
                        "status_code": response.status_code,
                        "url": self.url
                    }
                elif response.status_code in [401, 403]:
                    logger.error("InsForge authentication failed (HTTP 401/403).")
                    raise InsForgeClientError(f"InsForge authentication error (HTTP {response.status_code}). Check API credentials.")
                else:
                    logger.error(f"InsForge returned unexpected HTTP status: {response.status_code}")
                    raise InsForgeClientError(f"InsForge health check failed with HTTP status {response.status_code}")

        except httpx.RequestError as exc:
            logger.error(f"Network error connecting to InsForge: {exc}")
            raise InsForgeClientError(f"Network error connecting to InsForge at {self.url}: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected error checking InsForge connection: {exc}")
            raise InsForgeClientError(f"InsForge connectivity check failed: {exc}")
