"""Factory helpers for qBittorrent clients."""

from __future__ import annotations

from typing import Optional

from aiohttp import ClientSession

from .capabilities import QbitCapabilities
from .client import QbitClient


class QbitProviderFactory:
    """Creates qBittorrent clients while caching capability probes."""

    def __init__(self) -> None:
        self._capabilities: dict[str, QbitCapabilities] = {}

    async def ensure_capabilities(
        self,
        session: ClientSession,
        base_url: str,
        *,
        force_refresh: bool = False,
    ) -> QbitCapabilities:
        key = base_url.rstrip("/")
        if not force_refresh:
            cached = self._capabilities.get(key)
            if cached:
                return cached
        capabilities = await QbitCapabilities.probe(session, key)
        self._capabilities[key] = capabilities
        return capabilities

    def get_cached_capabilities(self, base_url: str) -> Optional[QbitCapabilities]:
        return self._capabilities.get(base_url.rstrip("/"))

    async def create_client(
        self,
        session: ClientSession,
        base_url: str,
        username: str,
        password: str,
        *,
        force_refresh_capabilities: bool = False,
    ) -> QbitClient:
        capabilities = await self.ensure_capabilities(
            session,
            base_url,
            force_refresh=force_refresh_capabilities,
        )
        return QbitClient(session, base_url, username, password, capabilities)

    async def test_connection(
        self,
        session: ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> QbitCapabilities:
        capabilities = await self.ensure_capabilities(
            session,
            base_url,
            force_refresh=True,
        )
        client = QbitClient(session, base_url, username, password, capabilities)
        await client.test_connection()
        return capabilities
