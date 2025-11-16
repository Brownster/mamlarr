from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


def load_settings() -> MamServiceSettings:
    """Helper used by FastAPI startup hooks."""
    return MamServiceSettings()  # type: ignore[call-arg]
