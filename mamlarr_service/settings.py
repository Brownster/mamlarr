from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchType(str, Enum):
    """Subset of search type choices exposed by Jackett for MAM."""

    active = "active"
    dying = "dying"
    dead = "dead"
    all = "all"


class MamServiceSettings(BaseSettings):
    """Runtime configuration for the MyAnonamouse download service."""

    api_key: str = Field(
        "dev-mam-service-key",
        description="API key required on every request.",
    )
    mam_session_id: str = Field(
        "dev-mam-session",
        description="Session cookie used to authenticate against MyAnonamouse.",
    )
    mam_base_url: str = Field(
        "https://www.myanonamouse.net",
        description="Base URL for the tracker.",
    )
    indexer_id: int = Field(
        801001,
        description="Synthetic indexer ID exposed to AudioBookRequest.",
    )
    indexer_name: str = Field("MyAnonamouse")
    download_directory: Path = Field(
        default=Path("/mnt/storage/audiobooks/"),
        description="Destination directory for processed audiobooks.",
    )
    search_category_id: int = Field(13, description="Default MyAnonamouse category for audiobooks.")
    search_type: SearchType = Field(
        SearchType.active,
        description="Which torrents to include when querying MAM.",
    )
    search_in_description: bool = Field(
        False,
        description="Include torrent descriptions when matching text queries.",
    )
    search_in_series: bool = Field(
        True,
        description="Include series metadata when matching text queries.",
    )
    search_in_filenames: bool = Field(
        False,
        description="Match terms that only appear in file names.",
    )
    search_languages: list[int] = Field(
        default_factory=list,
        description="Optional list of language IDs to filter results.",
    )
    search_ttl_seconds: int = Field(
        3600,
        description="TTL for cached search results.",
    )
    torrent_download_endpoint: str = Field(
        "/torrents.php?action=download&id={id}",
        description="Relative endpoint for downloading torrent files.",
    )
    seed_target_hours: int = Field(
        72,
        description="Minimum seeding duration required before processing.",
    )
    seed_check_interval_seconds: int = Field(
        300,
        description="Interval at which Transmission torrents are polled.",
    )
    remove_torrent_after_processing: bool = Field(
        True,
        description="Remove torrent from Transmission after processing completes.",
    )
    transmission_url: Optional[str] = Field(
        default=None,
        description="Transmission RPC endpoint.",
    )
    transmission_username: Optional[str] = Field(
        default=None,
        description="Transmission username.",
    )
    transmission_password: Optional[str] = Field(
        default=None,
        description="Transmission password.",
    )
    postprocess_tmp_dir: Path = Field(
        default=Path("/tmp/mam-service"),
        description="Temporary directory for ffmpeg concat files.",
    )
    enable_audio_merge: bool = Field(
        True,
        description="Attempt to merge multi-file audiobooks into a single container.",
    )
    use_mock_data: bool = Field(
        False,
        description="Use built-in mock tracker/transmission for local testing.",
    )
    qbittorrent_url: Optional[str] = Field(
        default=None,
        description="qBittorrent WebUI base URL (e.g. https://seedbox:443/api/v2).",
    )
    qbittorrent_username: Optional[str] = Field(default=None)
    qbittorrent_password: Optional[str] = Field(default=None)
    use_transmission: bool = Field(
        True,
        description="Transmission download provider enabled.",
    )
    use_qbittorrent: bool = Field(
        False,
        description="qBittorrent download provider enabled.",
    )
    user_ratio: float = Field(
        1.0,
        description="Current global ratio displayed in the UI.",
    )
    ratio_goal: float = Field(
        1.0,
        description="Target ratio goal for notifications.",
    )
    bonus_points: int = Field(
        0,
        description="Approximate bonus points/Karma from tracker.",
    )
    freeleech_alerts_enabled: bool = Field(
        True,
        description="Toggle dashboard alerts for freeleech torrents.",
    )

    model_config = SettingsConfigDict(
        env_prefix="MAM_SERVICE_",
        env_file=".env",
        extra="ignore",
    )

    @field_validator("search_languages", mode="before")
    @classmethod
    def _coerce_languages(
        cls, value: str | Iterable[int] | None
    ) -> list[int]:  # pragma: no cover - exercised through settings load
        if value is None or value == "":
            return []
        if isinstance(value, str):
            items = [chunk.strip() for chunk in value.split(",") if chunk.strip()]
            return [int(chunk) for chunk in items]
        if isinstance(value, Iterable):
            return [int(chunk) for chunk in value]
        raise TypeError("search_languages must be a comma separated string or iterable of ints")


def load_settings() -> MamServiceSettings:
    """Helper used by FastAPI startup hooks."""
    return MamServiceSettings()  # type: ignore[call-arg]
