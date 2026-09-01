from typing import Any, Dict, List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.utils.config import settings
from app.utils.logger import logger

class YouTubeClientError(Exception):
    """Base exception for YouTube API errors."""
    pass

class YouTubeQuotaExceededError(YouTubeClientError):
    """Raised when YouTube API quota is exceeded."""
    pass

class YouTubeAuthError(YouTubeClientError):
    """Raised when YouTube API authentication fails."""
    pass

class YouTubeClient:
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: Optional[str] = None, timeout: int = settings.REQUEST_TIMEOUT):
        if api_key is not None:
            key = api_key
        else:
            key = settings.YOUTUBE_API_KEY.get_secret_value() if settings.YOUTUBE_API_KEY else ""
        self.api_key = key.strip()
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        return {"Accept": "application/json"}

    def search_videos(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search videos via YouTube Data API v3.
        Returns normalized list of items containing: video_id, title, channel_id, channel_title, published_at.
        """
        if not self.api_key:
            raise YouTubeAuthError("YOUTUBE_API_KEY is not configured or empty.")

        url = f"{self.BASE_URL}/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
            "key": self.api_key
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params, headers=self._get_headers())
                
                if response.status_code == 400 or response.status_code == 403:
                    error_data = response.json().get("error", {})
                    errors = error_data.get("errors", [])
                    reason = errors[0].get("reason", "") if errors else ""
                    
                    if reason == "quotaExceeded":
                        logger.error("YouTube Data API quota exceeded.")
                        raise YouTubeQuotaExceededError("YouTube API quota exceeded.")
                    elif response.status_code == 403 or reason in ["keyInvalid", "badRequest"]:
                        logger.error("YouTube Data API authentication/key error.")
                        raise YouTubeAuthError(f"YouTube API authentication error: {error_data.get('message', 'Forbidden/Invalid Key')}")

                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP error during YouTube API search: {exc.response.status_code}")
            raise YouTubeClientError(f"HTTP error {exc.response.status_code}: {exc.response.text}")
        except httpx.RequestError as exc:
            logger.error(f"Request network error connecting to YouTube API: {exc}")
            raise YouTubeClientError(f"Network error connecting to YouTube API: {exc}")
        except ValueError as exc:
            logger.error(f"Invalid JSON response from YouTube API: {exc}")
            raise YouTubeClientError("Invalid JSON response received from YouTube API.")

        normalized_results = []
        items = data.get("items", [])
        for item in items:
            id_info = item.get("id", {})
            snippet = item.get("snippet", {})
            video_id = id_info.get("videoId")
            if not video_id:
                continue

            normalized_results.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_id": snippet.get("channelId", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", "")
            })

        return normalized_results
