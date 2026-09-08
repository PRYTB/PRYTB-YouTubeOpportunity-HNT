import re
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Iterable
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.utils.config import settings
from app.utils.logger import logger
from app.collectors.quota_tracker import QuotaTracker

T = TypeVar("T")

class YouTubeClientError(Exception):
    """Base exception for YouTube API errors."""
    pass

class YouTubeAuthError(YouTubeClientError):
    """Raised when YouTube API authentication fails or key is invalid."""
    pass

class YouTubeQuotaExceededError(YouTubeClientError):
    """Raised when YouTube API quota is exceeded."""
    pass

class YouTubeRateLimitError(YouTubeClientError):
    """Raised when YouTube API rate limiting (429) occurs."""
    pass

class YouTubeAPIError(YouTubeClientError):
    """Raised for server or API specific errors."""
    pass

class InvalidResponseError(YouTubeClientError):
    """Raised when YouTube API returns invalid JSON or malformed response."""
    pass


def parse_iso8601_duration(duration_str: Optional[str]) -> Optional[int]:
    """
    Parses ISO 8601 duration strings like PT45S, PT8M30S, PT1H2M5S into seconds.
    Returns None if missing or invalid.
    """
    if not duration_str:
        return None

    pattern = re.compile(
        r'^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$'
    )
    match = pattern.match(duration_str)
    if not match:
        return None

    parts = match.groupdict()
    days = int(parts['days'] or 0)
    hours = int(parts['hours'] or 0)
    minutes = int(parts['minutes'] or 0)
    seconds = int(parts['seconds'] or 0)

    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total_seconds


def parse_int_or_none(val: Any) -> Optional[int]:
    """
    Safely converts a value to integer or None.
    Handles None, empty string, non-digit strings, absent fields, unexpected types.
    """
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def chunked(items: List[T], batch_size: int) -> List[List[T]]:
    """
    Splits a list into chunks of at most batch_size.
    Handles 0, 1, 50, 51, 100 etc.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if not items:
        return []
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


class YouTubeClient:
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = settings.REQUEST_TIMEOUT,
        quota_tracker: Optional[QuotaTracker] = None
    ):
        if api_key is not None:
            key = api_key
        else:
            key = settings.YOUTUBE_API_KEY.get_secret_value() if settings.YOUTUBE_API_KEY else ""
        self.api_key = key.strip()
        self.timeout = timeout
        self.quota_tracker = quota_tracker or QuotaTracker()

    def _get_headers(self) -> Dict[str, str]:
        return {"Accept": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, YouTubeRateLimitError, YouTubeAPIError)),
        reraise=True
    )
    def _execute_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes HTTP GET request against YouTube API v3 with retries on transient errors.
        Permanent errors (400, 401, 403 permanent/quota) are NOT retried.
        """
        if not self.api_key:
            raise YouTubeAuthError("YOUTUBE_API_KEY is not configured or empty.")

        url = f"{self.BASE_URL}/{endpoint}"
        req_params = params.copy()
        req_params["key"] = self.api_key

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=req_params, headers=self._get_headers())
                status = response.status_code

                if status in (400, 401, 403, 429) or status >= 500:
                    try:
                        error_json = response.json()
                        error_data = error_json.get("error", {})
                        errors = error_data.get("errors", [])
                        reason = errors[0].get("reason", "") if errors else ""
                        msg = error_data.get("message", response.text)
                    except Exception:
                        reason = ""
                        msg = response.text

                    if reason in ("quotaExceeded", "dailyLimitExceeded", "quotaExceeded403") or "Quota exceeded" in msg or "quota" in msg.lower():
                        logger.error(f"YouTube API quota exceeded: {msg}")
                        raise YouTubeQuotaExceededError(f"YouTube API quota exceeded: {msg}")
                    elif status in (401, 403) or reason in ("keyInvalid", "badRequest", "unauthorized"):
                        logger.error(f"YouTube API authentication error: {msg}")
                        raise YouTubeAuthError(f"YouTube API authentication error: {msg}")
                    elif status == 429 or reason in ("rateLimitExceeded", "userRateLimitExceeded"):
                        logger.warning(f"YouTube API rate limit hit: {msg}")
                        raise YouTubeRateLimitError(f"Rate limit exceeded: {msg}")
                    elif status >= 500:
                        logger.warning(f"YouTube API server error ({status}): {msg}")
                        raise YouTubeAPIError(f"YouTube API server error ({status}): {msg}")
                    else:
                        raise YouTubeClientError(f"HTTP error {status}: {msg}")

                response.raise_for_status()
                return response.json()

        except httpx.RequestError as exc:
            logger.warning(f"Network error during YouTube API call ({endpoint}): {exc}")
            raise YouTubeAPIError(f"Network error connecting to YouTube API: {exc}") from exc
        except ValueError as exc:
            logger.error(f"Invalid JSON received from YouTube API ({endpoint}): {exc}")
            raise InvalidResponseError("Invalid JSON response received from YouTube API.") from exc

    def search_videos(
        self,
        query: str,
        max_results: int = 50,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        region_code: Optional[str] = None,
        relevance_language: Optional[str] = None,
        order: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Paginates search.list until max_results target is reached or nextPageToken is empty.
        Returns (items, page_count).
        """
        all_items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        page_count = 0

        while len(all_items) < max_results:
            page_count += 1
            remaining = max_results - len(all_items)
            page_size = min(remaining, 50)

            params: Dict[str, Any] = {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": page_size,
            }
            if page_token:
                params["pageToken"] = page_token
            if published_after:
                params["publishedAfter"] = published_after
            if published_before:
                params["publishedBefore"] = published_before
            if region_code:
                params["regionCode"] = region_code
            if relevance_language:
                params["relevanceLanguage"] = relevance_language
            if order:
                params["order"] = order

            data = self._execute_request("search", params)
            self.quota_tracker.track("search.list", 1)

            items = data.get("items", [])
            for item in items:
                snippet = item.get("snippet", {})
                id_info = item.get("id", {})
                video_id = id_info.get("videoId")
                if not video_id:
                    continue

                all_items.append({
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", "")
                })

            page_token = data.get("nextPageToken")
            if not page_token or not items:
                break

        return all_items[:max_results], page_count

    def get_videos(self, video_ids: List[str]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Executes videos.list in batches of 50 video IDs.
        Returns (video_items, batch_count).
        """
        if not video_ids:
            return [], 0

        batches = chunked(video_ids, 50)
        all_videos: List[Dict[str, Any]] = []

        for batch in batches:
            params = {
                "part": "snippet,statistics,contentDetails,status",
                "id": ",".join(batch)
            }
            data = self._execute_request("videos", params)
            self.quota_tracker.track("videos.list", 1)
            items = data.get("items", [])
            all_videos.extend(items)

        return all_videos, len(batches)

    def get_channels(self, channel_ids: List[str]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Executes channels.list in batches of 50 channel IDs.
        Returns (channel_items, batch_count).
        """
        if not channel_ids:
            return [], 0

        batches = chunked(channel_ids, 50)
        all_channels: List[Dict[str, Any]] = []

        for batch in batches:
            params = {
                "part": "snippet,statistics",
                "id": ",".join(batch)
            }
            data = self._execute_request("channels", params)
            self.quota_tracker.track("channels.list", 1)
            items = data.get("items", [])
            all_channels.extend(items)

        return all_channels, len(batches)
