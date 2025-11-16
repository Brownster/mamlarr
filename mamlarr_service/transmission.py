from __future__ import annotations

import base64
from typing import Any, Dict, Iterable, Optional

from aiohttp import BasicAuth, ClientSession

from .log import logger


class TransmissionError(RuntimeError):
    pass


class TransmissionClient:
    """Async wrapper around the Transmission RPC API."""

    def __init__(
        self,
        session: ClientSession,
        rpc_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._session = session
        self._rpc_url = rpc_url
        self._auth = BasicAuth(username, password) if username else None
        self._session_id: Optional[str] = None

    async def _rpc(self, method: str, arguments: Optional[dict] = None) -> dict:
        payload = {"method": method, "arguments": arguments or {}}
        headers: Dict[str, str] = {}
        if self._session_id:
            headers["X-Transmission-Session-Id"] = self._session_id

        for attempt in range(2):
            async with self._session.post(
                self._rpc_url,
                json=payload,
                headers=headers,
                auth=self._auth,
            ) as response:
                if response.status == 409:
                    self._session_id = response.headers.get("X-Transmission-Session-Id")
                    headers["X-Transmission-Session-Id"] = self._session_id or ""
                    continue
                if not response.ok:
                    text = await response.text()
                    raise TransmissionError(
                        f"RPC {method} failed: {response.status} {response.reason} {text}"
                    )
                data = await response.json()
                if data.get("result") != "success":
                    raise TransmissionError(
                        f"RPC {method} failed: {data.get('result')}"
                    )
                return data
        raise TransmissionError("Unable to negotiate Transmission session id")

    async def add_torrent(self, torrent_bytes: bytes) -> dict:
        arguments = {
            "metainfo": base64.b64encode(torrent_bytes).decode(),
        }
        data = await self._rpc("torrent-add", arguments)
        result = data["arguments"].get("torrent-added") or data["arguments"].get(
            "torrent-duplicate"
        )
        if not result:
            raise TransmissionError("Failed to add torrent, Transmission returned empty data")
        logger.info(
            "Transmission: torrent registered",
            torrent_id=result.get("id"),
            hash=result.get("hashString"),
        )
        return result

    async def get_torrents(self, hashes: Iterable[str]) -> dict[str, dict[str, Any]]:
        hash_list = list(hashes)
        if not hash_list:
            return {}
        arguments = {
            "fields": [
                "id",
                "name",
                "hashString",
                "status",
                "percentDone",
                "rateDownload",
                "rateUpload",
                "uploadedEver",
                "downloadDir",
                "leftUntilDone",
                "eta",
                "isFinished",
                "addedDate",
                "doneDate",
                "files",
            ],
            "ids": hash_list,
        }
        data = await self._rpc("torrent-get", arguments)
        torrents = data["arguments"].get("torrents", [])
        return {tor["hashString"]: tor for tor in torrents}

    async def remove_torrent(self, hash_string: str, delete_data: bool = False) -> None:
        await self._rpc(
            "torrent-remove",
            arguments={"ids": [hash_string], "delete-local-data": delete_data},
        )
        logger.info("Transmission: torrent removed", hash=hash_string)

    async def test_connection(self) -> None:
        await self._rpc("session-get")


class MockTransmissionClient:
    """In-memory Transmission replacement for offline testing."""

    def __init__(self, settings):
        from pathlib import Path
        import itertools

        self._counter = itertools.count(1)
        self._torrents: Dict[str, Dict[str, Any]] = {}
        self._staging_root = Path(settings.postprocess_tmp_dir) / "mock_transmission"
        self._staging_root.mkdir(parents=True, exist_ok=True)

    async def add_torrent(self, torrent_bytes: bytes) -> dict:
        torrent_id = next(self._counter)
        hash_string = f"mockhash{torrent_id}"
        name = f"mock_book_{torrent_id}"
        path = self._staging_root / f"torrent_{torrent_id}" / name
        path.mkdir(parents=True, exist_ok=True)
        audio_file = path / "track1.mp3"
        audio_file.write_bytes(b"fake audio data")
        info = {
            "id": torrent_id,
            "hashString": hash_string,
            "name": name,
            "downloadDir": str(self._staging_root / f"torrent_{torrent_id}"),
            "leftUntilDone": 1,
            "status": 4,
            "files": [
                {"name": f"{name}/track1.mp3"},
            ],
        }
        self._torrents[hash_string] = info
        return info

    async def get_torrents(self, hashes: Iterable[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for hash_string in hashes:
            info = self._torrents.get(hash_string)
            if not info:
                continue
            if info["leftUntilDone"] > 0:
                info["leftUntilDone"] = 0
                info["status"] = 6
            result[hash_string] = info
        return result

    async def remove_torrent(self, hash_string: str, delete_data: bool = False) -> None:
        self._torrents.pop(hash_string, None)

    async def test_connection(self) -> None:
        # nothing to test in mock mode
        return None
