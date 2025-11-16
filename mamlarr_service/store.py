from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from .models import CachedResult, DownloadJob, DownloadJobStatus, Release


class SearchResultStore:
    """Caches search results so download requests can be resolved later."""

    def __init__(self, ttl_seconds: int):
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()
        self._items: Dict[str, CachedResult] = {}

    async def save(self, release: Release, raw: dict) -> None:
        cached = CachedResult(guid=release.guid, release=release, raw=raw)
        async with self._lock:
            self._items[release.guid] = cached

    async def get(self, guid: str) -> Optional[CachedResult]:
        async with self._lock:
            cached = self._items.get(guid)
            if not cached:
                return None
            if datetime.utcnow() - cached.stored_at > self._ttl:
                del self._items[guid]
                return None
            return cached


class JobStore:
    """In-memory queue tracking torrent lifecycle state."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._jobs: Dict[str, DownloadJob] = {}

    async def enqueue(self, guid: str, source: dict, release: dict) -> DownloadJob:
        job = DownloadJob(id=str(uuid4()), guid=guid, source=source, release=release)
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> Optional[DownloadJob]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list_all(self) -> List[DownloadJob]:
        async with self._lock:
            return list(self._jobs.values())

    async def update_fields(
        self, job_id: str, *, message: Optional[str] = None, **fields
    ) -> Optional[DownloadJob]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if message is not None:
                fields["message"] = message
            updated = job.model_copy(
                update={**fields, "updated_at": datetime.utcnow()}
            )
            self._jobs[job_id] = updated
            return updated

    async def update_status(
        self,
        job_id: str,
        status: DownloadJobStatus,
        message: Optional[str] = None,
    ) -> Optional[DownloadJob]:
        return await self.update_fields(job_id, status=status, message=message)

    async def delete(self, job_id: str) -> bool:
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False
