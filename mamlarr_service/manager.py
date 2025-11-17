from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from aiohttp import ClientSession
from torf import Torrent as TorfTorrent

from .log import logger

from .models import CachedResult, DownloadJob, DownloadJobStatus
from .postprocess import PostProcessingError, PostProcessor
from .providers.qbit import QbitClient
from .settings import MamServiceSettings
from .store import JobStore
from .transmission import MockTransmissionClient, TransmissionClient, TransmissionError


class DownloadManager:
    def __init__(
        self,
        service_settings: MamServiceSettings,
        job_store: JobStore,
        http_session: ClientSession,
        *,
        qbittorrent_client: QbitClient | None = None,
    ):
        self.settings = service_settings
        self.job_store = job_store
        self.http_session = http_session
        self.queue: asyncio.Queue[tuple[DownloadJob, CachedResult]] = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.monitor_task: Optional[asyncio.Task] = None
        self.use_mock_data = service_settings.use_mock_data
        self.provider = (
            "qbittorrent"
            if service_settings.use_qbittorrent and not self.use_mock_data
            else "transmission"
        )
        self.postprocessor = PostProcessor(
            service_settings.download_directory,
            service_settings.postprocess_tmp_dir,
            enable_merge=service_settings.enable_audio_merge,
            http_session=http_session,
        )
        self.qbittorrent = qbittorrent_client
        if self.use_mock_data:
            self.transmission = MockTransmissionClient(service_settings)
            self.qbittorrent = None
        else:
            if self.provider == "qbittorrent":
                if not self.qbittorrent:
                    raise ValueError(
                        "qBittorrent is enabled but no client was provided to DownloadManager"
                    )
                self.transmission = None
            else:
                if not service_settings.transmission_url:
                    raise ValueError("Transmission URL must be configured")
                self.transmission = TransmissionClient(
                    http_session,
                    service_settings.transmission_url,
                    username=service_settings.transmission_username,
                    password=service_settings.transmission_password,
                )
        self._stopping = False

    async def start(self):
        if self.worker_task:
            return
        self.worker_task = asyncio.create_task(self._worker(), name="mam-worker")
        if not self.use_mock_data:
            self.monitor_task = asyncio.create_task(self._monitor(), name="mam-monitor")
        logger.info("MamService: download manager started")

    async def stop(self):
        self._stopping = True
        if self.worker_task:
            self.worker_task.cancel()
        if self.monitor_task:
            self.monitor_task.cancel()
        await asyncio.gather(
            *(t for t in (self.worker_task, self.monitor_task) if t), return_exceptions=True
        )

    async def submit(self, job: DownloadJob, cached: CachedResult) -> None:
        await self.queue.put((job, cached))

    async def _worker(self):
        while not self._stopping:
            try:
                job, cached = await self.queue.get()
            except asyncio.CancelledError:
                break
            try:
                await self._process_job(job, cached)
            except Exception as exc:
                logger.exception("MamService: job failed", job_id=job.id)
                await self.job_store.update_status(
                    job.id, DownloadJobStatus.failed, f"Job failed: {exc}"
                )
            finally:
                self.queue.task_done()

    async def _process_job(self, job: DownloadJob, cached: CachedResult):
        await self.job_store.update_status(
            job.id, DownloadJobStatus.downloading, "Downloading torrent metadata"
        )
        torrent_bytes = await self._download_torrent(cached.raw)
        await self.job_store.update_fields(job.id, torrent_id=str(cached.raw.get("id")))

        add_result = await self._add_torrent(torrent_bytes)
        await self.job_store.update_fields(
            job.id,
            transmission_id=add_result.get("id"),
            transmission_hash=add_result.get("hashString"),
            provider=self.provider,
            message=f"Torrent added to {self.provider}",
        )
        if self.use_mock_data:
            await self._complete_mock_job(job.id, add_result)

    async def _monitor(self):
        interval = max(30, self.settings.seed_check_interval_seconds)
        while not self._stopping:
            try:
                await asyncio.sleep(interval)
                await self._poll_torrents()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("MamService: monitor failed", error=str(exc))

    async def _poll_torrents(self):
        jobs = await self.job_store.list_all()
        hashes = [job.transmission_hash for job in jobs if job.transmission_hash]
        if not hashes:
            return
        torrent_map = await self._fetch_torrents(hashes)
        now = datetime.utcnow()

        for job in jobs:
            torrent_hash = job.transmission_hash
            if not torrent_hash:
                continue
            torrent = torrent_map.get(torrent_hash)
            if torrent is None:
                continue
            status = torrent.get("status")
            left = torrent.get("leftUntilDone", 0)
            if self.use_mock_data:
                logger.info(
                    "MamService: monitor tick",
                    job_id=job.id,
                    left=left,
                    torrent_status=status,
                    job_status=job.status,
                )
            if left == 0 and job.status == DownloadJobStatus.downloading:
                await self.job_store.update_fields(
                    job.id,
                    status=DownloadJobStatus.seeding,
                    completed_at=datetime.utcnow(),
                    message="Seeding to satisfy requirements",
                )
                job = (await self.job_store.get(job.id)) or job

            if job.status == DownloadJobStatus.seeding:
                await self._update_seeding(job, torrent, now)
                job = (await self.job_store.get(job.id)) or job

            if (
                job.status == DownloadJobStatus.seeding
                and job.seed_seconds >= self.settings.seed_target_hours * 3600
            ):
                await self.job_store.update_status(
                    job.id,
                    DownloadJobStatus.processing,
                    "Seeding requirement met, processing release",
                )
                asyncio.create_task(self._finalize_job(job.id, torrent))

    async def _update_seeding(self, job: DownloadJob, torrent: dict, now: datetime):
        seeding_statuses = {5, 6}
        status = torrent.get("status")
        last = job.last_seed_timestamp or now
        if status in seeding_statuses:
            elapsed = max(0, (now - last).total_seconds())
            await self.job_store.update_fields(
                job.id,
                seed_seconds=job.seed_seconds + int(elapsed),
                last_seed_timestamp=now,
            )
        else:
            await self.job_store.update_fields(job.id, last_seed_timestamp=now)

    async def _finalize_job(self, job_id: str, torrent_snapshot: dict):
        job = await self.job_store.get(job_id)
        if not job:
            return
        try:
            destination = await self.postprocessor.process(job, torrent_snapshot)
            await self.job_store.update_fields(
                job_id,
                status=DownloadJobStatus.completed,
                destination_path=str(destination),
                message=f"Completed -> {destination}",
            )
            if (
                self.settings.remove_torrent_after_processing
                and job.transmission_hash
                and not self.use_mock_data
            ):
                await self._remove_torrent(job.transmission_hash)
        except PostProcessingError as exc:
            await self.job_store.update_status(
                job_id, DownloadJobStatus.failed, f"Post-processing failed: {exc}"
            )
        except TransmissionError as exc:
            await self.job_store.update_status(
                job_id, DownloadJobStatus.failed, f"Transmission error: {exc}"
            )

    async def _complete_mock_job(self, job_id: str, torrent_snapshot: dict):
        await self.job_store.update_fields(
            job_id,
            status=DownloadJobStatus.seeding,
            completed_at=datetime.utcnow(),
            message="Mock seeding complete",
            seed_seconds=int(self.settings.seed_target_hours * 3600),
        )
        await self.job_store.update_status(
            job_id, DownloadJobStatus.processing, "Processing mock download"
        )
        await self._finalize_job(job_id, torrent_snapshot)

    async def _add_torrent(self, torrent_bytes: bytes) -> dict:
        if self.use_mock_data or self.provider == "transmission":
            assert self.transmission is not None
            return await self.transmission.add_torrent(torrent_bytes)
        assert self.qbittorrent is not None
        await self.qbittorrent.add_torrent(torrent_bytes)
        info_hash = TorfTorrent.read_stream(torrent_bytes).infohash.upper()
        return {"hashString": info_hash}

    async def _fetch_torrents(self, hashes: list[str]) -> dict[str, dict]:
        if self.use_mock_data or self.provider == "transmission":
            assert self.transmission is not None
            return await self.transmission.get_torrents(hashes)
        result: dict[str, dict] = {}
        assert self.qbittorrent is not None
        torrents = await self.qbittorrent.list_torrents(hashes)
        for tor in torrents:
            hash_string = (tor.get("hash") or "").upper()
            if not hash_string:
                continue
            total = tor.get("total_size") or tor.get("size") or 0
            downloaded = tor.get("downloaded") or 0
            left = max(0, total - downloaded)
            files_raw = await self.qbittorrent.list_files(hash_string)
            files = [{"name": f.get("name")} for f in files_raw]
            result[hash_string] = {
                "status": self._map_qb_state(tor.get("state")),
                "leftUntilDone": left,
                "downloadDir": tor.get("save_path"),
                "name": tor.get("name"),
                "files": files,
            }
        return result

    def _map_qb_state(self, state: Optional[str]) -> int:
        if not state:
            return 0
        state = state.lower()
        seeding = {"uploading", "stalledup", "queuedup", "forcedup", "checkingup"}
        if state in seeding:
            return 6
        return 4

    async def _remove_torrent(self, hash_string: str) -> None:
        if self.use_mock_data:
            return
        if self.provider == "transmission":
            assert self.transmission is not None
            await self.transmission.remove_torrent(hash_string, delete_data=False)
        else:
            assert self.qbittorrent is not None
            await self.qbittorrent.remove_torrent(hash_string, delete_data=False)

    async def _download_torrent(self, raw: dict) -> bytes:
        if self.settings.use_mock_data:
            return b"mock-torrent-data"
        torrent_id = raw.get("id") or raw.get("tid") or raw.get("tor_id")
        if not torrent_id:
            raise ValueError("Unable to determine torrent id from search result")
        endpoint = self.settings.torrent_download_endpoint.format(id=torrent_id)
        url = urljoin(self.settings.mam_base_url, endpoint)
        logger.info("MamService: downloading torrent file", torrent_id=torrent_id)
        async with self.http_session.get(
            url, cookies={"mam_id": self.settings.mam_session_id}
        ) as response:
            if response.status == 403:
                raise PermissionError("Torrent download forbidden (check session id)")
            if not response.ok:
                text = await response.text()
                raise RuntimeError(
                    f"Failed to download torrent {torrent_id}: {response.status} {text}"
                )
            return await response.read()
