from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from aiohttp import ClientError, ClientSession
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .log import logger

from .mam_client import AuthenticationError, MyAnonamouseClient, SearchError
from .manager import DownloadManager
from .models import DownloadJob, DownloadJobStatus, IndexerInfo, Release
from .settings import MamServiceSettings, load_settings
from .settings_store import SettingsStore
from .store import JobStore, SearchResultStore
from .transmission import TransmissionClient


class DownloadRequest(BaseModel):
    guid: str
    indexerId: int


class DownloadResponse(BaseModel):
    status: str
    jobId: str


class JobResponse(BaseModel):
    job: DownloadJob


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_title(result: dict[str, Any], fallback: str) -> str:
    for key in (
        "title",
        "name",
        "torTitle",
        "torname",
        "rawName",
        "book_title",
        "torrent_name",
    ):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _coerce_datetime(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(tz=timezone.utc).isoformat()


def _extract_size(raw: dict[str, Any]) -> int:
    for key in ("size", "size_bytes", "bytes", "filesize", "torrent_size"):
        if raw.get(key) is not None:
            return _coerce_int(raw[key])
    return 0


def _extract_seeders(raw: dict[str, Any]) -> int:
    for key in ("seeders", "seed", "seeders_total", "leech_seeders"):
        if raw.get(key) is not None:
            return _coerce_int(raw[key])
    return 0


def _extract_leechers(raw: dict[str, Any]) -> int:
    for key in ("leechers", "leeches", "leech", "leechers_total"):
        if raw.get(key) is not None:
            return _coerce_int(raw[key])
    return 0


def _split_multi_value(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    values: list[str] = []
    for entry in raw:
        if not entry:
            continue
        parts = [chunk.strip() for chunk in entry.split(",") if chunk.strip()]
        values.extend(parts)
    return values


def _parse_int_filters(raw: list[str] | None) -> list[int]:
    values: list[int] = []
    for chunk in _split_multi_value(raw):
        try:
            values.append(int(chunk))
        except ValueError:
            logger.debug("MamService: ignoring invalid filter", value=chunk)
    return values


def _determine_guid(raw: dict[str, Any]) -> str:
    for key in ("id", "tid", "tor_id", "torrent_id"):
        value = raw.get(key)
        if value:
            return f"mam-{value}"
    return f"mam-{uuid4()}"


def _flags_from_result(raw: dict[str, Any]) -> list[str]:
    flags: set[str] = set()
    if raw.get("personal_freeleech") in (1, "1", True):
        flags.update({"personal_freeleech", "freeleech"})
    if raw.get("free") in (1, "1", True):
        flags.update({"free", "freeleech"})
    if raw.get("fl_vip") in (1, "1", True):
        flags.update({"fl_vip", "freeleech"})
    if raw.get("vip") in (1, "1", True):
        flags.add("vip")
    return sorted(flags)


def create_app(settings: Optional[MamServiceSettings] = None) -> FastAPI:
    service_settings = settings or load_settings()
    settings_store = SettingsStore(
        Path(__file__).parent.parent / "data" / "settings.json"
    )
    overrides = settings_store.load()
    if overrides:
        merged = {**service_settings.model_dump(), **overrides}
        service_settings = MamServiceSettings(**merged)
    app = FastAPI(title="MyAnonamouse Download Service")
    app.state.settings = service_settings
    app.state.search_store = SearchResultStore(service_settings.search_ttl_seconds)
    app.state.job_store = JobStore()
    app.state.http_session = None
    app.state.mam_client = None
    app.state.manager: DownloadManager | None = None
    app.state.settings_store = settings_store

    async def _get_http_session() -> ClientSession:
        session = app.state.http_session
        if session is None:
            session = ClientSession()
            app.state.http_session = session
        return session
    app.state.get_http_session = _get_http_session

    async def _get_mam_client() -> MyAnonamouseClient:
        client = app.state.mam_client
        if client is None:
            http_session = await _get_http_session()
            client = MyAnonamouseClient(http_session, service_settings)
            app.state.mam_client = client
        return client
    app.state.get_mam_client = _get_mam_client

    async def _restart_manager(current_settings: MamServiceSettings):
        manager = app.state.manager
        if manager:
            await manager.stop()
        if current_settings.use_mock_data or current_settings.transmission_url:
            http_session = await _get_http_session()
            manager = DownloadManager(
                service_settings=current_settings,
                job_store=app.state.job_store,
                http_session=http_session,
            )
            app.state.manager = manager
            await manager.start()
        else:
            app.state.manager = None

    async def _apply_settings_update(
        changes: dict[str, Any],
        *,
        restart_manager: bool = False,
        reset_mam_client: bool = False,
    ) -> MamServiceSettings:
        overrides = settings_store.update(changes)
        merged = app.state.settings.model_dump()
        merged.update(overrides)
        new_settings = MamServiceSettings(**merged)
        app.state.settings = new_settings
        if reset_mam_client:
            app.state.mam_client = None
        if restart_manager:
            await _restart_manager(new_settings)
        return new_settings

    app.state.restart_manager = _restart_manager
    app.state.apply_settings_update = _apply_settings_update

    async def _toggle_provider(*, use_transmission: Optional[bool] = None, use_qbittorrent: Optional[bool] = None):
        current = app.state.settings
        new_transmission = current.use_transmission if use_transmission is None else use_transmission
        new_qb = current.use_qbittorrent if use_qbittorrent is None else use_qbittorrent
        if new_transmission and new_qb:
            raise HTTPException(status_code=400, detail="Only one download provider can be enabled at a time.")
        if not new_transmission and not new_qb:
            raise HTTPException(status_code=400, detail="At least one download provider must remain enabled.")
        await _apply_settings_update(
            {"use_transmission": new_transmission, "use_qbittorrent": new_qb},
            restart_manager=True,
        )

    async def require_api_key(x_api_key: str = Header(..., alias="X-Api-Key")) -> None:
        if x_api_key != service_settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

    @app.on_event("startup")
    async def _startup():
        http_session = await _get_http_session()
        await _get_mam_client()
        await _restart_manager(app.state.settings)
        logger.info("MamService: started", indexer_id=app.state.settings.indexer_id)

    @app.on_event("shutdown")
    async def _shutdown():
        session: ClientSession | None = app.state.http_session
        if session and not session.closed:
            await session.close()
        manager = app.state.manager
        if manager:
            await manager.stop()
        logger.info("MamService: shutdown complete")

    @app.get("/health")
    async def healthcheck():
        return {"status": "ok"}

    @app.get("/api/v1/indexer")
    async def indexers(_: None = Depends(require_api_key)):
        info = IndexerInfo(
            id=service_settings.indexer_id,
            name=service_settings.indexer_name,
        )
        return [info.model_dump()]

    async def _map_release(
        result: dict[str, Any], fallback_title: str
    ) -> Optional[Release]:
        guid = _determine_guid(result)
        title = _coerce_title(result, fallback_title)
        publish_date = _coerce_datetime(result.get("added") or result.get("timestamp"))
        size = _extract_size(result)
        seeders = _extract_seeders(result)
        leechers = _extract_leechers(result)
        info_url = None
        for key in ("id", "tid", "tor_id", "torrent_id"):
            if result.get(key):
                info_url = f"{service_settings.mam_base_url.rstrip('/')}/t/{result[key]}"
                break

        return Release(
            guid=guid,
            indexerId=service_settings.indexer_id,
            indexer=service_settings.indexer_name,
            title=title,
            seeders=seeders,
            leechers=leechers,
            size=size,
            infoUrl=info_url,
            indexerFlags=_flags_from_result(result),
            publishDate=publish_date,
        )

    @app.get("/api/v1/search")
    async def search(
        _: None = Depends(require_api_key),
        query: str = Query(...),
        limit: int = Query(100),
        offset: int = Query(0),
        search_type: str = Query("search", alias="type"),
        categories: list[str] | None = Query(None, alias="cat"),
        languages: list[str] | None = Query(None, alias="lang"),
    ):
        del search_type  # not used but kept for parity with Prowlarr
        category_filters = _parse_int_filters(categories)
        language_filters = _parse_int_filters(languages)
        try:
            client = await _get_mam_client()
            results = await client.search(
                query=query,
                limit=limit,
                offset=offset,
                categories=category_filters,
                languages=language_filters,
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except SearchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        releases: list[Release] = []
        for result in results:
            release = await _map_release(result, fallback_title=query)
            if release is None:
                continue
            await app.state.search_store.save(release, result)
            releases.append(release)
        return [r.model_dump() for r in releases]

    @app.post("/api/v1/search", response_model=DownloadResponse)
    async def push_release(
        payload: DownloadRequest,
        _: None = Depends(require_api_key),
    ):
        if payload.indexerId != service_settings.indexer_id:
            raise HTTPException(status_code=404, detail="Indexer not recognised")
        cached = await app.state.search_store.get(payload.guid)
        if cached is None:
            raise HTTPException(
                status_code=404,
                detail="Unknown or expired release guid",
            )
        job = await app.state.job_store.enqueue(
            payload.guid, cached.raw, cached.release.model_dump()
        )
        logger.info(
            "MamService: queued download",
            guid=payload.guid,
            job_id=job.id,
        )
        manager: DownloadManager | None = app.state.manager
        if manager is None:
            raise HTTPException(status_code=503, detail="Transmission not configured")
        await manager.submit(job, cached)
        return DownloadResponse(status="queued", jobId=job.id)

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
    async def job_status(
        job_id: str,
        _: None = Depends(require_api_key),
    ):
        job = await app.state.job_store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobResponse(job=job)

    @app.put("/mamlarr/api/settings/mam-session")
    async def update_mam_session(request: Request):
        data = await request.form()
        session_id = (data.get("session_id") or "").strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        await _apply_settings_update(
            {"mam_session_id": session_id}, reset_mam_client=True
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/mam-url")
    async def update_mam_url(request: Request):
        data = await request.form()
        base_url = (data.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise HTTPException(status_code=400, detail="base_url is required")
        await _apply_settings_update({"mam_base_url": base_url}, reset_mam_client=True)
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/transmission-url")
    async def update_transmission_url(request: Request):
        data = await request.form()
        url = (data.get("url") or "").strip() or None
        await _apply_settings_update(
            {"transmission_url": url},
            restart_manager=True,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/qb-url")
    async def update_qb_url(request: Request):
        data = await request.form()
        url = (data.get("url") or "").strip() or None
        await _apply_settings_update({"qbittorrent_url": url})
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/transmission-username")
    async def update_transmission_username(request: Request):
        data = await request.form()
        username = (data.get("username") or "").strip() or None
        await _apply_settings_update(
            {"transmission_username": username},
            restart_manager=bool(app.state.settings.transmission_url)
            or app.state.settings.use_mock_data,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/transmission-password")
    async def update_transmission_password(request: Request):
        data = await request.form()
        password = (data.get("password") or "").strip() or None
        await _apply_settings_update(
            {"transmission_password": password},
            restart_manager=bool(app.state.settings.transmission_url)
            or app.state.settings.use_mock_data,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/qb-username")
    async def update_qb_username(request: Request):
        data = await request.form()
        username = (data.get("username") or "").strip() or None
        await _apply_settings_update({"qbittorrent_username": username})
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/qb-password")
    async def update_qb_password(request: Request):
        data = await request.form()
        password = (data.get("password") or "").strip() or None
        await _apply_settings_update({"qbittorrent_password": password})
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/seed-hours")
    async def update_seed_hours(request: Request):
        data = await request.form()
        raw_hours = data.get("hours")
        try:
            hours = max(0, float(raw_hours))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="hours must be numeric")
        await _apply_settings_update(
            {"seed_target_hours": hours},
            restart_manager=True,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/download-dir")
    async def update_download_dir(request: Request):
        data = await request.form()
        directory = (data.get("directory") or "").strip()
        if not directory:
            raise HTTPException(status_code=400, detail="directory is required")
        await _apply_settings_update(
            {"download_directory": directory},
            restart_manager=True,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    def _toggle_value(value: Optional[str], current: bool) -> bool:
        if value is None:
            return not current
        lowered = value.lower()
        if lowered in {"toggle", ""}:
            return not current
        return lowered in {"true", "1", "yes", "on"}

    @app.put("/mamlarr/api/settings/audio-merge")
    async def update_audio_merge(request: Request):
        data = await request.form()
        new_value = _toggle_value(
            data.get("enabled"), app.state.settings.enable_audio_merge
        )
        await _apply_settings_update(
            {"enable_audio_merge": new_value},
            restart_manager=True,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/auto-remove")
    async def update_auto_remove(request: Request):
        data = await request.form()
        new_value = _toggle_value(
            data.get("enabled"),
            app.state.settings.remove_torrent_after_processing,
        )
        await _apply_settings_update(
            {"remove_torrent_after_processing": new_value},
            restart_manager=True,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/api-key")
    async def update_api_key(request: Request):
        data = await request.form()
        api_key = (data.get("api_key") or "").strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="api_key is required")
        await _apply_settings_update({"api_key": api_key})
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/mock-mode")
    async def update_mock_mode(request: Request):
        data = await request.form()
        new_value = _toggle_value(
            data.get("enabled"),
            app.state.settings.use_mock_data,
        )
        await _apply_settings_update(
            {"use_mock_data": new_value},
            restart_manager=True,
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/use-transmission")
    async def set_use_transmission():
        await _toggle_provider(use_transmission=True, use_qbittorrent=False)
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/use-qbittorrent")
    async def set_use_qbittorrent():
        await _toggle_provider(use_transmission=False, use_qbittorrent=True)
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/ratio")
    async def update_ratio(request: Request):
        data = await request.form()
        try:
            current_ratio = float(
                data.get("current_ratio", app.state.settings.user_ratio)
            )
            ratio_goal = float(data.get("ratio_goal", app.state.settings.ratio_goal))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="ratio must be numeric")
        await _apply_settings_update(
            {"user_ratio": current_ratio, "ratio_goal": ratio_goal}
        )
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/bonus")
    async def update_bonus_points(request: Request):
        data = await request.form()
        try:
            bonus = int(data.get("bonus_points", app.state.settings.bonus_points))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail="bonus_points must be an integer"
            )
        await _apply_settings_update({"bonus_points": max(0, bonus)})
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.put("/mamlarr/api/settings/freeleech-alerts")
    async def update_freeleech_alerts(request: Request):
        data = await request.form()
        new_value = _toggle_value(
            data.get("enabled"), app.state.settings.freeleech_alerts_enabled
        )
        await _apply_settings_update({"freeleech_alerts_enabled": new_value})
        return Response(status_code=204, headers={"HX-Trigger": "mamlarr:settings"})

    @app.post("/mamlarr/api/test-connection")
    async def test_connection():
        settings = app.state.settings
        if settings.use_mock_data:
            return HTMLResponse(
                "<div class='text-success text-sm'>Mock mode enabled - connection OK.</div>"
            )
        manager = app.state.manager
        if settings.use_qbittorrent:
            qb_client = getattr(manager, "qbittorrent", None) if manager else None
            if qb_client is None:
                raise HTTPException(
                    status_code=400,
                    detail="qBittorrent is enabled but not configured or running.",
                )
            try:
                await qb_client.test_connection()
            except Exception as exc:
                logger.warning("qBittorrent test failed", error=str(exc))
                return HTMLResponse(
                    f"<div class='text-error text-sm'>qBittorrent connection failed: {exc}</div>",
                    status_code=502,
                )
            return HTMLResponse(
                "<div class='text-success text-sm'>qBittorrent API reachable.</div>"
            )

        if not settings.transmission_url:
            raise HTTPException(
                status_code=400, detail="Transmission URL not configured."
            )
        if manager and not settings.use_mock_data:
            client = manager.transmission
        else:
            http_session = await _get_http_session()
            client = TransmissionClient(
                http_session,
                settings.transmission_url,
                username=settings.transmission_username,
                password=settings.transmission_password,
            )
        try:
            await client.test_connection()
        except ClientError as exc:
            logger.warning("Transmission test failed", error=str(exc))
            return HTMLResponse(
                f"<div class='text-error text-sm'>Connection failed: {exc}</div>",
                status_code=502,
            )
        except Exception as exc:
            logger.error("Transmission test error", error=str(exc))
            return HTMLResponse(
                "<div class='text-error text-sm'>Unexpected error testing Transmission. "
                "Check logs for details.</div>",
                status_code=500,
            )
        return HTMLResponse(
            "<div class='text-success text-sm'>Transmission RPC reachable.</div>"
        )

    @app.delete("/mamlarr/api/jobs/{job_id}")
    async def delete_job(job_id: str):
        job = await app.state.job_store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        manager = app.state.manager
        if job.transmission_hash and manager:
            try:
                await manager._remove_torrent(job.transmission_hash)
            except Exception as exc:
                logger.error("Failed to remove torrent", error=str(exc))
        await app.state.job_store.delete(job_id)
        warning = (
            "<div class='alert alert-warning text-xs'>Removed from queue. "
            "Remember trackers still require you to meet seeding obligations.</div>"
        )
        return HTMLResponse(warning)

    # Include UI router
    from .ui import create_ui_router
    # When running standalone, mount shared static assets so UI has CSS/JS.
    # Try multiple possible locations for static files
    possible_static_dirs = [
        Path("/srv/audiobookrequest/static"),  # Docker container
        Path(__file__).resolve().parents[3] / "static",  # Local development
        Path(__file__).resolve().parents[2] / "static",  # Alternate location
    ]
    static_dir = None
    for path in possible_static_dirs:
        if path.exists():
            static_dir = path
            break

    if static_dir:
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    ui_router = create_ui_router(service_settings)
    app.include_router(ui_router)

    return app


app = create_app()
