from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, Sequence
from urllib.parse import urlencode, urljoin

from aiohttp import ClientSession

from .log import logger
from .mam_categories import tracker_categories_for_torznab
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

    _QUERY_SANITIZER = re.compile(r"[^\w]+", re.IGNORECASE)

    def _sanitize_query(self, query: str) -> str:
        """Normalize the search term to match Jackett's behaviour."""

        sanitized = self._QUERY_SANITIZER.sub(" ", query or "").strip()
        return sanitized

    async def search(
        self,
        query: str,
        limit: int = 100,
        offset: int = 0,
        *,
        categories: Sequence[int] | Iterable[int] | None = None,
        languages: Sequence[int] | Iterable[int] | None = None,
    ) -> list[dict]:
        if self._settings.use_mock_data:
            return MOCK_RESULTS
        sanitized_query = self._sanitize_query(query)
        if query and query.strip() and not sanitized_query:
            logger.debug(
                "MamService: search term empty after sanitization", query=query
            )
            return []

        params: Dict[str, Any] = {
            "tor[text]": sanitized_query,
            "tor[searchType]": self._settings.search_type.value,
            "tor[srchIn][title]": "true",
            "tor[srchIn][author]": "true",
            "tor[srchIn][narrator]": "true",
            "tor[searchIn]": "torrents",
            "tor[sortType]": "default",
            "tor[perpage]": max(1, limit) if limit else 100,
            "tor[startNumber]": max(0, offset),
            "thumbnails": "1",
            "description": "1",
        }

        if self._settings.search_in_description:
            params["tor[srchIn][description]"] = "true"
        if self._settings.search_in_series:
            params["tor[srchIn][series]"] = "true"
        if self._settings.search_in_filenames:
            params["tor[srchIn][filenames]"] = "true"

        selected_languages: Iterable[int] | Sequence[int] | None = (
            languages if languages else self._settings.search_languages
        )
        if selected_languages:
            for idx, lang in enumerate(selected_languages):
                try:
                    lang_id = int(lang)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                params[f"tor[browse_lang][{idx}]"] = str(lang_id)

        tracker_categories = tracker_categories_for_torznab(categories)
        if not tracker_categories and self._settings.search_category_id:
            tracker_categories = [self._settings.search_category_id]
        if tracker_categories:
            for idx, cat_id in enumerate(tracker_categories):
                params[f"tor[cat][{idx}]"] = str(cat_id)
        else:
            params["tor[cat][]"] = "0"

        endpoint = f"/tor/js/loadSearchJSONbasic.php?{urlencode(params, doseq=True)}"
        url = urljoin(self._settings.mam_base_url, endpoint)

        logger.debug("MamService: querying MAM", url=url)
        async with self._http_session.get(
            url, cookies={"mam_id": self._settings.mam_session_id}
        ) as response:
            text = await response.text()
            if response.status == 403:
                raise AuthenticationError("Failed to authenticate with MyAnonamouse")
            if not response.ok:
                logger.error(
                    "MamService: search failed",
                    status=response.status,
                    reason=response.reason,
                    body=text,
                )
                raise SearchError(f"MAM query failed: {response.status}")
            if text.strip().startswith("Error"):
                raise SearchError(text.strip())
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("MamService: unable to decode response", body=text)
                return []

        if isinstance(payload, dict) and "error" in payload:
            error_message = str(payload["error"])
            if error_message.lower().startswith("nothing returned"):
                return []
            raise SearchError(error_message)

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            logger.warning("MamService: unexpected payload structure", payload=payload)
            return []
        return data
