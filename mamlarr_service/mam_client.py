from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlencode, urljoin

from aiohttp import ClientSession

from .log import logger

from .settings import MamServiceSettings


class MyAnonamouseClientError(RuntimeError):
    pass


class AuthenticationError(MyAnonamouseClientError):
    pass


class SearchError(MyAnonamouseClientError):
    pass


MOCK_RESULTS = [
    {
        "id": 1001,
        "title": "Mock Audiobook",
        "seeders": 15,
        "leechers": 0,
        "size": 123_456_789,
        "tor_id": 1001,
        "added": "2024-01-01T00:00:00Z",
    }
]


class MyAnonamouseClient:
    """Thin wrapper around the MyAnonamouse JSON search endpoint."""

    def __init__(self, http_session: ClientSession, settings: MamServiceSettings):
        self._http_session = http_session
        self._settings = settings

    async def search(self, query: str, limit: int = 100, offset: int = 0) -> list[dict]:
        if self._settings.use_mock_data:
            return MOCK_RESULTS
        params: Dict[str, Any] = {
            "tor[text]": query,
            "tor[main_cat]": [self._settings.search_category_id],
            "tor[searchIn]": "torrents",
            "tor[srchIn][author]": "true",
            "tor[srchIn][title]": "true",
            "tor[searchType]": "active",
            "startNumber": offset,
            "perpage": limit,
        }

        endpoint = f"/tor/js/loadSearchJSONbasic.php?{urlencode(params, doseq=True)}"
        url = urljoin(self._settings.mam_base_url, endpoint)

        logger.debug("MamService: querying MAM", url=url)
        async with self._http_session.get(
            url, cookies={"mam_id": self._settings.mam_session_id}
        ) as response:
            if response.status == 403:
                raise AuthenticationError("Failed to authenticate with MyAnonamouse")
            if not response.ok:
                text = await response.text()
                logger.error(
                    "MamService: search failed",
                    status=response.status,
                    reason=response.reason,
                    body=text,
                )
                raise SearchError(f"MAM query failed: {response.status}")
            payload = await response.json(content_type=None)

        if isinstance(payload, dict) and "error" in payload:
            raise SearchError(str(payload["error"]))

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            logger.warning("MamService: unexpected payload structure", payload=payload)
            return []
        return data
