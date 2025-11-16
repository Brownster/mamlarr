from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Sequence
from uuid import uuid4
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
        "language": "EN",
        "filetype": "M4B",
        "added": "2024-01-01T00:00:00Z",
        "author_info": json.dumps(["Mock Author"]),
    }
]


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_datetime(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(tz=timezone.utc).isoformat()


def _coerce_title(result: dict[str, Any], fallback: str) -> str:
    for key in (
        "title",
        "name",
        "torTitle",
        "torname",
        "rawName",
        "book_title",
        "torrent_name",
    ):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _extract_size(raw: dict[str, Any]) -> int:
    for key in ("size", "size_bytes", "bytes", "filesize", "torrent_size"):
        if raw.get(key) is not None:
            return _coerce_int(raw[key])
    return 0


def _extract_seeders(raw: dict[str, Any]) -> int:
    for key in ("seeders", "seed", "seeders_total", "leech_seeders"):
        if raw.get(key) is not None:
            return _coerce_int(raw[key])
    return 0


def _extract_leechers(raw: dict[str, Any]) -> int:
    for key in ("leechers", "leeches", "leech", "leechers_total"):
        if raw.get(key) is not None:
            return _coerce_int(raw[key])
    return 0


def _determine_guid(raw: dict[str, Any]) -> str:
    for key in ("id", "tid", "tor_id", "torrent_id"):
        value = raw.get(key)
        if value:
            return f"mam-{value}"
    return f"mam-{uuid4()}"


def _flags_from_result(raw: dict[str, Any]) -> list[str]:
    flags: set[str] = set()
    if raw.get("personal_freeleech") in (1, "1", True):
        flags.update({"personal_freeleech", "freeleech"})
    if raw.get("free") in (1, "1", True):
        flags.update({"free", "freeleech"})
    if raw.get("fl_vip") in (1, "1", True):
        flags.update({"fl_vip", "freeleech"})
    if raw.get("vip") in (1, "1", True):
        flags.add("vip")
    return sorted(flags)


def _parse_people(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if isinstance(v, (str, int)) and str(v).strip()]
    if isinstance(value, dict):
        return [str(v).strip() for v in value.values() if v and str(v).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return _parse_people(parsed)
        except Exception:
            value = value.strip()
            return [value] if value else []
    return []


def _first_value(raw: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


@dataclass
class MamSearchResult:
    guid: str
    title: str
    link: str
    details: str
    size: int
    seeders: int
    leechers: int
    peers: int
    publish_date: str
    download_volume_factor: float
    minimum_seed_time: int
    flags: list[str]
    raw: dict[str, Any] = field(repr=False)


class MyAnonamouseClient:
    """Thin wrapper around the MyAnonamouse JSON search endpoint."""

    MINIMUM_SEED_TIME = 259200  # 72 hours

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
    ) -> list[MamSearchResult]:
        sanitized_query = self._sanitize_query(query)
        if self._settings.use_mock_data:
            return self._normalize_results(MOCK_RESULTS, sanitized_query or query)
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
        return self._normalize_results(data, sanitized_query or query)

    def _normalize_results(
        self, payload: list[dict[str, Any]], fallback: str
    ) -> list[MamSearchResult]:
        normalized: list[MamSearchResult] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            result = self._normalize_result(raw, fallback)
            if result:
                normalized.append(result)
        return normalized

    def _normalize_result(
        self, raw: dict[str, Any], fallback: str
    ) -> MamSearchResult | None:
        guid = _determine_guid(raw)
        title = self._decorate_title(raw, fallback)
        publish_date = _coerce_datetime(raw.get("added") or raw.get("timestamp"))
        size = _extract_size(raw)
        seeders = _extract_seeders(raw)
        leechers = _extract_leechers(raw)
        flags = _flags_from_result(raw)
        torrent_id = self._extract_torrent_id(raw)
        link = self._build_download_link(torrent_id)
        details = self._build_details_link(torrent_id)
        peers = seeders + leechers
        download_volume_factor = 0.0 if self._is_free(flags, raw) else 1.0
        return MamSearchResult(
            guid=guid,
            title=title,
            link=link,
            details=details,
            size=size,
            seeders=seeders,
            leechers=leechers,
            peers=peers,
            publish_date=publish_date,
            download_volume_factor=download_volume_factor,
            minimum_seed_time=self.MINIMUM_SEED_TIME,
            flags=flags,
            raw=raw,
        )

    def _decorate_title(self, raw: dict[str, Any], fallback: str) -> str:
        base = _coerce_title(raw, fallback)
        authors = _parse_people(raw.get("author_info"))
        if authors:
            base = f"{base} - {', '.join(authors)}"
        markers: list[str] = []
        language = _first_value(
            raw, ("language", "lang", "lang_name", "language_name")
        )
        if language:
            markers.append(language.upper())
        filetype = _first_value(
            raw,
            ("filetype", "file_type", "torFileType", "format", "container"),
        )
        if filetype:
            markers.append(filetype.upper())
        if raw.get("vip") in (1, "1", True):
            markers.append("VIP")
        if raw.get("fl_vip") in (1, "1", True):
            markers.append("FL-VIP")
        if markers:
            marker_text = "".join(f"[{marker}]" for marker in markers)
            base = f"{base} {marker_text}".strip()
        return base

    def _extract_torrent_id(self, raw: dict[str, Any]) -> str | None:
        for key in ("id", "tid", "tor_id", "torrent_id"):
            value = raw.get(key)
            if value is not None:
                return str(value)
        return None

    def _build_details_link(self, torrent_id: str | None) -> str:
        if not torrent_id:
            return self._settings.mam_base_url.rstrip("/")
        return f"{self._settings.mam_base_url.rstrip('/')}/t/{torrent_id}"

    def _build_download_link(self, torrent_id: str | None) -> str:
        if not torrent_id:
            return self._settings.mam_base_url.rstrip("/")
        endpoint = self._settings.torrent_download_endpoint.format(id=torrent_id)
        return urljoin(self._settings.mam_base_url, endpoint)

    @staticmethod
    def _is_free(flags: list[str], raw: dict[str, Any]) -> bool:
        if any(flag in {"free", "freeleech", "personal_freeleech"} for flag in flags):
            return True
        return raw.get("personal_freeleech") in (1, "1", True)
