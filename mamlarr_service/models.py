from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Release(BaseModel):
    """Prowlarr-compatible release payload."""

    protocol: Literal["torrent"] = "torrent"
    guid: str
    indexerId: int
    indexer: str
    title: str
    seeders: int = 0
    leechers: int = 0
    size: int = 0
    infoUrl: Optional[str] = None
    indexerFlags: list[str] = Field(default_factory=list)
    downloadUrl: Optional[str] = None
    magnetUrl: Optional[str] = None
    publishDate: str
    peers: int = 0
    downloadVolumeFactor: float = 1.0
    minimumSeedTime: int = 0


class CachedResult(BaseModel):
    guid: str
    release: Release
    raw: dict[str, Any]
    stored_at: datetime = Field(default_factory=datetime.utcnow)


class IndexerInfo(BaseModel):
    id: int
    name: str
    enable: bool = True
    privacy: str = "private"


class DownloadJobStatus(str, Enum):
    queued = "queued"
    downloading = "downloading"
    seeding = "seeding"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DownloadJob(BaseModel):
    id: str
    guid: str
    status: DownloadJobStatus = DownloadJobStatus.queued
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    message: Optional[str] = None
    source: dict[str, Any] = Field(default_factory=dict)
    release: dict[str, Any] = Field(default_factory=dict)
    torrent_id: Optional[str] = None
    transmission_id: Optional[int] = None
    transmission_hash: Optional[str] = None
    download_dir: Optional[str] = None
    completed_at: Optional[datetime] = None
    seed_seconds: int = 0
    last_seed_timestamp: Optional[datetime] = None
    destination_path: Optional[str] = None
    provider: str = "transmission"
