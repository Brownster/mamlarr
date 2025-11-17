from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

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
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .log import logger

from .mam_client import (
    AuthenticationError,
    MamSearchResult,
    MyAnonamouseClient,
    SearchError,
)
from .manager import DownloadManager
from .models import DownloadJob, DownloadJobStatus, IndexerInfo, Release
from .providers.qbit import QbitClientError, QbitProviderFactory
from .settings import (
    QBIT_CATEGORY_PATTERN,
    QbitContentLayout,
    QbitInitialState,
    MamServiceSettings,
    load_settings,
)
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


class SessionCreationHelp(BaseModel):
    securityPreferencesUrl: str
    steps: list[str]
    inactivityWarning: str


class SearchFilterEnvInfo(BaseModel):
    name: str
    description: str
    default: Any


class ConfigResponse(BaseModel):
    indexerId: int
    indexerName: str
    sessionCreation: SessionCreationHelp
    searchFilters: list[SearchFilterEnvInfo]


SESSION_CREATION_URL = "https://www.myanonamouse.net/preferences/index.php?view=security"
SESSION_CREATION_STEPS = [
    "Log into MyAnonamouse in a browser.",
    "Open My Account → Security → Security Preferences.",
    "In the Session Creation panel, name a session (for example, 'mamlarr') and optionally lock it to your server's IP.",
    "Click Create Session and copy the mam_id value for the new entry.",
    "Paste that cookie into MAM_SERVICE_MAM_SESSION_ID or the UI settings page, then restart/reload mamlarr.",
]
INACTIVITY_WARNING = (
    "To prevent your account from being disabled for inactivity, you must log in and use the tracker regularly. "
    "If you will be away for an extended period, park your account in the MyAnonamouse preferences."
)


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


def _success_response() -> HTMLResponse:
    return HTMLResponse("", headers={"HX-Trigger": "mamlarr:settings"})


def _validation_error(message: str) -> HTMLResponse:
    return HTMLResponse(
        f"<span class=\"text-error text-xs\">{message}</span>",
        status_code=200,
    )


def _connection_test_response(
    message: str,
    *,
    success: bool,
    accepts_json: bool,
    hint: str | None = None,
    status_code: int = 200,
) -> Response:
    if accepts_json:
        payload = {
            "status": "ok" if success else "error",
            "message": message,
            "hint": hint,
        }
        return JSONResponse(payload, status_code=status_code)
    tone = "text-success" if success else "text-error"
    html = f"<div class='text-sm {tone}'>{message}</div>"
    if hint:
        html += f"<div class='text-xs opacity-70 mt-1'>{hint}</div>"
    return HTMLResponse(html, status_code=status_code)


def _normalize_category(value: str | None, *, required: bool) -> str | None:
    trimmed = (value or "").strip()
    if not trimmed:
        if required:
            raise ValueError("Category cannot be empty")
        return None
    if not QBIT_CATEGORY_PATTERN.match(trimmed):
        raise ValueError("Cannot contain \\\"\\\\\\\", '//', or start/end with '/'")
    return trimmed


def _parse_seed_ratio(value: str | None) -> Optional[float]:
    trimmed = (value or "").strip()
    if not trimmed:
        return None
    try:
        ratio = float(trimmed)
    except ValueError as exc:  # pragma: no cover - defensive, validated in tests
        raise ValueError("Seed ratio must be a number") from exc
    if ratio < 1.0:
        raise ValueError("Seed ratio must be at least 1.0")
    return round(ratio, 2)


def _parse_seed_time(value: str | None) -> Optional[int]:
    trimmed = (value or "").strip()
    if not trimmed:
        return None
    try:
        minutes = int(trimmed)
    except ValueError as exc:
        raise ValueError("Seed time must be an integer number of minutes") from exc
    if minutes < 1:
        raise ValueError("Seed time must be at least 1 minute")
    return minutes


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
    app.state.qbit_factory = QbitProviderFactory()

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
        should_start = (
            current_settings.use_mock_data
            or bool(current_settings.transmission_url)
            or (
                current_settings.use_qbittorrent
                and not current_settings.use_mock_data
            )
        )
        if not should_start:
            app.state.manager = None
            return

        http_session = await _get_http_session()
        qb_client = None
        if (
            current_settings.use_qbittorrent
            and not current_settings.use_mock_data
        ):
            if not (
                current_settings.qbittorrent_url
                and current_settings.qbittorrent_username
                and current_settings.qbittorrent_password
            ):
                raise ValueError("qBittorrent credentials are required when enabled")
            qb_client = await app.state.qbit_factory.create_client(
                http_session,
                current_settings.qbittorrent_url,
                current_settings.qbittorrent_username,
                current_settings.qbittorrent_password,
            )

        manager = DownloadManager(
            service_settings=current_settings,
            job_store=app.state.job_store,
            http_session=http_session,
            qbittorrent_client=qb_client,
        )
        app.state.manager = manager
        await manager.start()

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

    @app.get("/config", response_model=ConfigResponse)
    async def config():
        settings = app.state.settings
        search_filters = [
            SearchFilterEnvInfo(
                name="MAM_SERVICE_SEARCH_TYPE",
                description="Which torrents to include when querying MyAnonamouse (all, active, fl, fl-VIP, VIP, nVIP).",
                default=settings.search_type.value,
            ),
            SearchFilterEnvInfo(
                name="MAM_SERVICE_SEARCH_IN_DESCRIPTION",
                description="Include matches found only in the torrent description text.",
                default=settings.search_in_description,
            ),
            SearchFilterEnvInfo(
                name="MAM_SERVICE_SEARCH_IN_SERIES",
                description="Include matches based on the series metadata field.",
                default=settings.search_in_series,
            ),
            SearchFilterEnvInfo(
                name="MAM_SERVICE_SEARCH_IN_FILENAMES",
                description="Allow filename-only matches (slower but can catch sparse releases).",
                default=settings.search_in_filenames,
            ),
            SearchFilterEnvInfo(
                name="MAM_SERVICE_SEARCH_LANGUAGES",
                description="Comma-separated list of MyAnonamouse language IDs to restrict search results.",
                default=settings.search_languages,
            ),
        ]
        session_creation = SessionCreationHelp(
            securityPreferencesUrl=SESSION_CREATION_URL,
            steps=SESSION_CREATION_STEPS,
            inactivityWarning=INACTIVITY_WARNING,
        )
        return ConfigResponse(
            indexerId=settings.indexer_id,
            indexerName=settings.indexer_name,
            sessionCreation=session_creation,
            searchFilters=search_filters,
        )

    async def _map_release(result: MamSearchResult) -> Optional[Release]:
        return Release(
            guid=result.guid,
            indexerId=service_settings.indexer_id,
            indexer=service_settings.indexer_name,
            title=result.title,
            seeders=result.seeders,
            leechers=result.leechers,
            size=result.size,
            infoUrl=result.details,
            indexerFlags=result.flags,
            publishDate=result.publish_date,
            downloadUrl=result.link,
            peers=result.peers,
            downloadVolumeFactor=result.download_volume_factor,
            minimumSeedTime=result.minimum_seed_time,
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
            release = await _map_release(result)
            if release is None:
                continue
            await app.state.search_store.save(release, result.raw)
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
        return _success_response()

    @app.put("/mamlarr/api/settings/mam-url")
    async def update_mam_url(request: Request):
        data = await request.form()
        base_url = (data.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise HTTPException(status_code=400, detail="base_url is required")
        await _apply_settings_update({"mam_base_url": base_url}, reset_mam_client=True)
        return _success_response()

    @app.put("/mamlarr/api/settings/transmission-url")
    async def update_transmission_url(request: Request):
        data = await request.form()
        url = (data.get("url") or "").strip() or None
        await _apply_settings_update(
            {"transmission_url": url},
            restart_manager=True,
        )
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-url")
    async def update_qb_url(request: Request):
        data = await request.form()
        url = (data.get("url") or "").strip() or None
        await _apply_settings_update({"qbittorrent_url": url})
        return _success_response()

    @app.put("/mamlarr/api/settings/transmission-username")
    async def update_transmission_username(request: Request):
        data = await request.form()
        username = (data.get("username") or "").strip() or None
        await _apply_settings_update(
            {"transmission_username": username},
            restart_manager=bool(app.state.settings.transmission_url)
            or app.state.settings.use_mock_data,
        )
        return _success_response()

    @app.put("/mamlarr/api/settings/transmission-password")
    async def update_transmission_password(request: Request):
        data = await request.form()
        password = (data.get("password") or "").strip() or None
        await _apply_settings_update(
            {"transmission_password": password},
            restart_manager=bool(app.state.settings.transmission_url)
            or app.state.settings.use_mock_data,
        )
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-username")
    async def update_qb_username(request: Request):
        data = await request.form()
        username = (data.get("username") or "").strip() or None
        await _apply_settings_update({"qbittorrent_username": username})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-password")
    async def update_qb_password(request: Request):
        data = await request.form()
        password = (data.get("password") or "").strip() or None
        await _apply_settings_update({"qbittorrent_password": password})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-category")
    async def update_qb_category(request: Request):
        data = await request.form()
        try:
            category = _normalize_category(data.get("category"), required=True)
        except ValueError as exc:
            return _validation_error(str(exc))
        await _apply_settings_update({"qbittorrent_category": category})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-post-category")
    async def update_qb_post_category(request: Request):
        data = await request.form()
        try:
            category = _normalize_category(data.get("category"), required=False)
        except ValueError as exc:
            return _validation_error(str(exc))
        await _apply_settings_update({"qbittorrent_post_import_category": category})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-initial-state")
    async def update_qb_initial_state(request: Request):
        data = await request.form()
        raw_state = (data.get("initial_state") or "").strip()
        try:
            state = QbitInitialState(raw_state)
        except ValueError:
            return _validation_error("Select a valid initial state")
        await _apply_settings_update({"qbittorrent_initial_state": state.value})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-sequential")
    async def update_qb_sequential(request: Request):
        data = await request.form()
        current = app.state.settings.qbittorrent_sequential
        new_value = _toggle_value(data.get("enabled"), current)
        await _apply_settings_update({"qbittorrent_sequential": new_value})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-content-layout")
    async def update_qb_content_layout(request: Request):
        data = await request.form()
        raw_layout = (data.get("content_layout") or "").strip()
        try:
            layout = QbitContentLayout(raw_layout)
        except ValueError:
            return _validation_error("Select a valid content layout")
        await _apply_settings_update({"qbittorrent_content_layout": layout.value})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-seed-ratio")
    async def update_qb_seed_ratio(request: Request):
        data = await request.form()
        try:
            ratio = _parse_seed_ratio(data.get("seed_ratio"))
        except ValueError as exc:
            return _validation_error(str(exc))
        await _apply_settings_update({"qbittorrent_seed_ratio": ratio})
        return _success_response()

    @app.put("/mamlarr/api/settings/qb-seed-time")
    async def update_qb_seed_time(request: Request):
        data = await request.form()
        try:
            minutes = _parse_seed_time(data.get("seed_time"))
        except ValueError as exc:
            return _validation_error(str(exc))
        await _apply_settings_update({"qbittorrent_seed_time": minutes})
        return _success_response()

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
        return _success_response()

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
    async def test_connection(request: Request):
        accepts_json = "application/json" in (request.headers.get("accept", "").lower())
        settings = app.state.settings
        if settings.use_mock_data:
            return _connection_test_response(
                "Mock mode enabled - connection OK.",
                success=True,
                accepts_json=accepts_json,
            )
        manager = app.state.manager
        if settings.use_qbittorrent:
            if not (
                settings.qbittorrent_url
                and settings.qbittorrent_username
                and settings.qbittorrent_password
            ):
                raise HTTPException(
                    status_code=400,
                    detail="qBittorrent is enabled but credentials are missing.",
                )
            http_session = await _get_http_session()
            try:
                capabilities = await app.state.qbit_factory.test_connection(
                    http_session,
                    settings.qbittorrent_url,
                    settings.qbittorrent_username,
                    settings.qbittorrent_password,
                )
            except QbitClientError as exc:
                logger.warning(
                    "qBittorrent test failed",
                    error=str(exc),
                    hint=getattr(exc, "hint", None),
                )
                return _connection_test_response(
                    f"qBittorrent connection failed: {exc}",
                    success=False,
                    hint=getattr(exc, "hint", None),
                    status_code=502,
                    accepts_json=accepts_json,
                )
            except Exception as exc:
                logger.warning("qBittorrent test failed", error=str(exc))
                return _connection_test_response(
                    "qBittorrent connection failed. Check the server logs for details.",
                    success=False,
                    status_code=502,
                    accepts_json=accepts_json,
                )
            return _connection_test_response(
                f"qBittorrent API reachable (web API v{capabilities.api_major}).",
                success=True,
                accepts_json=accepts_json,
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
            return _connection_test_response(
                f"Connection failed: {exc}",
                success=False,
                hint="Verify the Transmission RPC URL, credentials, and that RPC access is enabled.",
                status_code=502,
                accepts_json=accepts_json,
            )
        except Exception as exc:
            logger.error("Transmission test error", error=str(exc))
            return _connection_test_response(
                "Unexpected error testing Transmission. Check logs for details.",
                success=False,
                status_code=500,
                accepts_json=accepts_json,
            )
        return _connection_test_response(
            "Transmission RPC reachable.",
            success=True,
            accepts_json=accepts_json,
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
