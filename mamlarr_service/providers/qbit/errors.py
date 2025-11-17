"""Shared qBittorrent error hierarchy."""

from __future__ import annotations


class QbitClientError(RuntimeError):
    """Base exception for qBittorrent provider failures."""

    def __init__(self, message: str, *, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


class AuthenticationError(QbitClientError):
    """Raised when qBittorrent rejects our credentials or cookies."""

    def __init__(
        self,
        message: str = "qBittorrent rejected the supplied credentials.",
        *,
        hint: str | None = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or "Confirm the WebUI username/password and that this host is on the WebUI IP whitelist.",
        )


class QueueingDisabledError(QbitClientError):
    """Raised when queueing is disabled in qBittorrent and we cannot add torrents."""

    def __init__(
        self,
        message: str = "qBittorrent queueing is disabled, so torrents cannot be enqueued.",
        *,
        hint: str | None = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or "Enable queueing under Tools → Options → Downloads or reduce the number of queued jobs in Mamlarr.",
        )


class CertValidationError(QbitClientError):
    """Raised when TLS validation fails while contacting qBittorrent."""

    def __init__(
        self,
        message: str = "Could not verify qBittorrent's TLS certificate.",
        *,
        hint: str | None = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or "Import the qBittorrent certificate into the trust store or disable HTTPS verification only if you fully trust the host.",
        )


class CapabilityProbeError(QbitClientError):
    """Raised when we cannot determine the qBittorrent Web API capabilities."""

    def __init__(
        self,
        message: str = "Unable to determine qBittorrent Web API version.",
        *,
        hint: str | None = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or "Verify the base URL is correct and that qBittorrent exposes the WebUI endpoints.",
        )


class HTTPStatusError(QbitClientError):
    """Raised when the qBittorrent API returns an unexpected HTTP status."""

    def __init__(
        self,
        status: int,
        reason: str,
        body: str,
        *,
        hint: str | None = None,
    ) -> None:
        detail = body.strip() or "No response body provided"
        super().__init__(
            f"qBittorrent API error {status}: {reason or 'Unknown'} ({detail})",
            hint=hint,
        )
        self.status = status
        self.reason = reason
        self.body = body
