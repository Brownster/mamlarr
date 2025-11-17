"""qBittorrent provider helpers."""

from .add_torrent import QbitAddOptions
from .capabilities import QbitCapabilities
from .client import QbitClient
from .errors import (
    AuthenticationError,
    CapabilityProbeError,
    CertValidationError,
    HTTPStatusError,
    QbitClientError,
    QueueingDisabledError,
)
from .factory import QbitProviderFactory

__all__ = [
    "AuthenticationError",
    "CapabilityProbeError",
    "CertValidationError",
    "HTTPStatusError",
    "QbitAddOptions",
    "QbitCapabilities",
    "QbitClient",
    "QbitClientError",
    "QbitProviderFactory",
    "QueueingDisabledError",
]
