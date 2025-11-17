"""Helpers for translating qBittorrent add options."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...settings import QbitContentLayout
from .capabilities import QbitCapabilities


@dataclass(frozen=True)
class QbitAddOptions:
    """Configurable qBittorrent parameters for new torrents."""

    category: str | None = None
    start_paused: bool | None = None
    force_start: bool | None = None
    sequential: bool | None = None
    content_layout: QbitContentLayout | None = None
    ratio_limit: float | None = None
    seeding_time_limit: int | None = None


@dataclass(frozen=True)
class QbitAddRequest:
    """Represents the endpoint + payload used to add a torrent."""

    path: str
    form_fields: dict[str, str] = field(default_factory=dict)


class QbitAddRequestBuilder:
    """Translates ``QbitAddOptions`` into API-specific form fields."""

    def __init__(self, capabilities: QbitCapabilities) -> None:
        self._capabilities = capabilities

    def build(self, options: QbitAddOptions | None = None) -> QbitAddRequest:
        use_v2 = self._capabilities.prefers_v2()
        path = "api/v2/torrents/add" if use_v2 else "command/upload"
        opts = options or QbitAddOptions()
        fields: dict[str, str] = {}
        if opts.category:
            fields["category"] = opts.category
        if opts.start_paused is not None:
            pause_key = "stopped" if use_v2 else "paused"
            fields[pause_key] = _bool_str(opts.start_paused)
        if opts.force_start is not None:
            force_key = "forced" if use_v2 else "forceStart"
            fields[force_key] = _bool_str(opts.force_start)
        if opts.sequential:
            fields["sequentialDownload"] = _bool_str(True)
        if opts.content_layout and opts.content_layout != QbitContentLayout.default:
            layout_value = _map_content_layout(opts.content_layout)
            if layout_value:
                fields["contentLayout"] = layout_value
        if opts.ratio_limit is not None:
            fields["ratioLimit"] = str(opts.ratio_limit)
        if opts.seeding_time_limit is not None:
            fields["seedingTimeLimit"] = str(opts.seeding_time_limit)
        return QbitAddRequest(path=path, form_fields=fields)


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _map_content_layout(layout: QbitContentLayout) -> str | None:
    if layout == QbitContentLayout.original:
        return "Original"
    if layout == QbitContentLayout.subfolder:
        return "Subfolder"
    return None
