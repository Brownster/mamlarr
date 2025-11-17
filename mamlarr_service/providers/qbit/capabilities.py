"""qBittorrent capability probing utilities."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from aiohttp import ClientSession

from ...log import logger
from .errors import CapabilityProbeError


@dataclass(frozen=True)
class QbitCapabilities:
    """Represents the supported qBittorrent Web API surface."""

    api_major: int
    supported_endpoints: frozenset[str]

    _PROBE_ENDPOINTS: tuple[str, ...] = (
        "/api/v2/app/webapiVersion",
        "/api/v2/app/version",
        "/version/api",
    )

    @classmethod
    async def probe(
        cls, session: ClientSession, base_url: str, *, timeout: float | None = None
    ) -> "QbitCapabilities":
        """Query the qBittorrent Web API to learn which endpoints are supported."""

        base = base_url.rstrip("/")
        found: set[str] = set()
        api_major: int | None = None
        for path in cls._PROBE_ENDPOINTS:
            url = urljoin(f"{base}/", path.lstrip("/"))
            try:
                async with session.get(url, timeout=timeout) as response:
                    if response.status >= 400:
                        logger.debug(
                            "qBittorrent: capability probe failed", path=path, status=response.status
                        )
                        continue
                    body = await response.text()
                    found.add(path)
                    if api_major is None:
                        api_major = cls._parse_major(body)
                        if api_major is not None:
                            logger.info(
                                "qBittorrent: detected Web API", api_major=api_major, path=path
                            )
            except asyncio.TimeoutError:
                logger.warning("qBittorrent: capability probe timeout", path=path)
            except Exception as exc:  # pragma: no cover - network edge cases
                logger.debug("qBittorrent: capability probe exception", path=path, error=str(exc))
        if api_major is None:
            raise CapabilityProbeError(
                "Unable to determine qBittorrent Web API version."
            )
        if not found:
            raise CapabilityProbeError(
                "qBittorrent Web API does not expose a recognizable version endpoint."
            )
        return cls(api_major=api_major, supported_endpoints=frozenset(found))

    @staticmethod
    def _parse_major(raw: str) -> int | None:
        match = re.search(r"(\d+)", raw)
        if not match:
            return None
        return int(match.group(1))

    def supports(self, endpoint: str) -> bool:
        normalized = endpoint if endpoint.startswith("/") else f"/{endpoint.lstrip('/')}"
        return normalized in self.supported_endpoints

    def prefers_v2(self) -> bool:
        return any(path.startswith("/api/v2") for path in self.supported_endpoints)
