from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin

from aiohttp import ClientSession, FormData

from .log import logger


class QbitClientError(RuntimeError):
    pass


class AuthenticationError(QbitClientError):
    pass


class QbitClient:
    """Thin wrapper around the qBittorrent WebUI API (v2)."""

    def __init__(
        self,
        http_session: ClientSession,
        base_url: str,
        username: str,
        password: str,
    ):
        self._session = http_session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._authenticated = False

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = urljoin(f"{self._base_url}/", path.lstrip("/"))
        resp = await self._session.request(method, url, **kwargs)
        if resp.status == 403:
            raise AuthenticationError("qBittorrent authentication failed")
        if not resp.ok:
            text = await resp.text()
            raise QbitClientError(
                f"qBittorrent API error {resp.status}: {resp.reason} ({text})"
            )
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return await resp.json()
        return await resp.text()

    async def _ensure_auth(self) -> None:
        if self._authenticated:
            return
        data = {
            "username": self._username,
            "password": self._password,
        }
        resp = await self._session.post(
            urljoin(f"{self._base_url}/", "api/v2/auth/login"), data=data
        )
        body = await resp.text()
        if resp.status != 200 or body != "Ok.":
            raise AuthenticationError("Failed to login to qBittorrent")
        self._authenticated = True
        logger.info("qBittorrent: authenticated successfully")

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
