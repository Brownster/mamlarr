"""Shared qBittorrent error hierarchy."""

from __future__ import annotations


class QbitClientError(RuntimeError):
    """Base exception for qBittorrent provider failures."""


class AuthenticationError(QbitClientError):
    """Raised when qBittorrent rejects our credentials or cookies."""


class QueueingDisabledError(QbitClientError):
    """Raised when queueing is disabled in qBittorrent and we cannot add torrents."""


class CertValidationError(QbitClientError):
    """Raised when TLS validation fails while contacting qBittorrent."""


class CapabilityProbeError(QbitClientError):
    """Raised when we cannot determine the qBittorrent Web API capabilities."""


class HTTPStatusError(QbitClientError):
    """Raised when the qBittorrent API returns an unexpected HTTP status."""

    def __init__(self, status: int, reason: str, body: str):
        super().__init__(
            f"qBittorrent API error {status}: {reason or 'Unknown'} ({body.strip()})"
        )
        self.status = status
        self.reason = reason
        self.body = body
