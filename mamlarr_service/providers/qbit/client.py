"""Async qBittorrent client with cookie + capability handling."""

from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin

from aiohttp import ClientError, ClientSession, FormData
from aiohttp.client_exceptions import (
    ClientConnectorCertificateError,
    ClientConnectorSSLError,
)
from yarl import URL

from ...log import logger
from .capabilities import QbitCapabilities
from .errors import (
    AuthenticationError,
    CertValidationError,
    HTTPStatusError,
    QbitClientError,
    QueueingDisabledError,
)


class QbitClient:
    """Thin wrapper around the qBittorrent WebUI API (v2)."""

    _COOKIE_CACHE: dict[str, SimpleCookie[str]] = {}

    def __init__(
        self,
        http_session: ClientSession,
        base_url: str,
        username: str,
        password: str,
        capabilities: QbitCapabilities,
    ):
        self._session = http_session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._capabilities = capabilities
        self._authenticated = False
        self._cookie_key = self._base_url
        self._load_cached_cookies()

    @property
    def capabilities(self) -> QbitCapabilities:
        return self._capabilities

    def _load_cached_cookies(self) -> None:
        cached = self._COOKIE_CACHE.get(self._cookie_key)
        if cached:
            self._session.cookie_jar.update_cookies(cached, URL(self._base_url))
            self._authenticated = True

    def _persist_cookies(self) -> None:
        cookies = self._session.cookie_jar.filter_cookies(URL(self._base_url))
        if cookies:
            self._COOKIE_CACHE[self._cookie_key] = cookies

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = urljoin(f"{self._base_url}/", path.lstrip("/"))
        for attempt in range(2):
            try:
                async with self._session.request(method, url, **kwargs) as resp:
                    if resp.status == 403 and attempt == 0:
                        await self._handle_forbidden()
                        continue
                    return await self._decode_response(resp)
            except (ClientConnectorCertificateError, ClientConnectorSSLError) as exc:
                raise CertValidationError("TLS validation failed for qBittorrent") from exc
            except ClientError as exc:
                raise QbitClientError(f"qBittorrent request failed: {exc}") from exc
        raise AuthenticationError("qBittorrent authentication failed")

    async def _handle_forbidden(self) -> None:
        self._authenticated = False
        await self._login(force=True)

    async def _decode_response(self, resp):
        if resp.status == 403:
            raise AuthenticationError("qBittorrent authentication failed")
        if resp.status == 409:
            body = await resp.text()
            if "queue" in body.lower():
                raise QueueingDisabledError(
                    "qBittorrent queueing is disabled. Enable it or adjust slots."
                )
            raise HTTPStatusError(resp.status, resp.reason, body)
        if resp.status >= 400:
            body = await resp.text()
            raise HTTPStatusError(resp.status, resp.reason, body)
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return await resp.json()
        return await resp.text()

    async def _login(self, *, force: bool = False) -> None:
        if self._authenticated and not force:
            return
        data = {
            "username": self._username,
            "password": self._password,
        }
        async with self._session.post(
            urljoin(f"{self._base_url}/", "api/v2/auth/login"), data=data
        ) as resp:
            body = await resp.text()
            if resp.status != 200 or body.strip() != "Ok.":
                raise AuthenticationError("Failed to login to qBittorrent")
        self._authenticated = True
        self._persist_cookies()
        logger.info(
            "qBittorrent: authenticated", api_major=self._capabilities.api_major
        )

    async def _ensure_auth(self) -> None:
        await self._login()

    async def add_torrent(self, torrent_bytes: bytes) -> None:
        await self._ensure_auth()
        form = FormData()
        form.add_field(
            "torrents",
            torrent_bytes,
            filename="download.torrent",
            content_type="application/x-bittorrent",
        )
        await self._request("POST", "api/v2/torrents/add", data=form)
        logger.info("qBittorrent: torrent added")

    async def list_torrents(self, hashes: Optional[Iterable[str]] = None) -> list[dict]:
        await self._ensure_auth()
        params: Dict[str, Any] = {}
        if hashes:
            params["hashes"] = "|".join(hashes)
        data = await self._request("GET", "api/v2/torrents/info", params=params)
        if isinstance(data, list):
            return data
        return []

    async def remove_torrent(self, hash_string: str, delete_data: bool = False) -> None:
        await self._ensure_auth()
        await self._request(
            "POST",
            "api/v2/torrents/delete",
            data={
                "hashes": hash_string,
                "deleteFiles": "true" if delete_data else "false",
            },
        )
        logger.info("qBittorrent: torrent removed", hash=hash_string)

    async def test_connection(self) -> None:
        await self._ensure_auth()
        await self._request("GET", "api/v2/app/version")

    async def list_files(self, hash_string: str) -> list[dict]:
        await self._ensure_auth()
        data = await self._request(
            "GET", "api/v2/torrents/files", params={"hash": hash_string}
        )
        if isinstance(data, list):
            return data
        return []
