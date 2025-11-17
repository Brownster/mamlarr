"""
UI routes for Mamlarr web interface.
Serves Jinja2 templates matching AudioBookRequest's design.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .log import logger
from .models import DownloadJobStatus
from .settings import MamServiceSettings

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/mamlarr", tags=["ui"])


def get_base_context(request: Request, settings: MamServiceSettings) -> dict:
    """Get common template context variables"""
    return {
        "request": request,
        "base_url": "",  # Assuming root-relative URLs
        "version": "0.1.0",  # TODO: Get from package
        "settings": settings,
    }


@router.get("/", response_class=HTMLResponse, name="dashboard")
async def dashboard(request: Request):
    """Main dashboard showing active downloads and recent activity"""
    # Get app state
    app = request.app
    settings: MamServiceSettings = app.state.settings
    job_store = app.state.job_store

    # Get all jobs
    all_jobs = await job_store.list_all()

    # Categorize jobs
    active_jobs = [
        job
        for job in all_jobs
        if job.status in [DownloadJobStatus.downloading, DownloadJobStatus.seeding]
    ]
    completed_jobs = [
        job
        for job in all_jobs
        if job.status == DownloadJobStatus.completed
    ]
    # Sort completed by completion time
    completed_jobs.sort(key=lambda j: j.completed_at or j.updated_at, reverse=True)

    # Calculate stats
    stats = {
        "active_count": len(active_jobs),
        "downloading_count": len([j for j in all_jobs if j.status == DownloadJobStatus.downloading]),
        "seeding_count": len([j for j in all_jobs if j.status == DownloadJobStatus.seeding]),
        "completed_count": len(completed_jobs),
        "completed_today": len([
            j for j in completed_jobs
            if j.completed_at and j.completed_at > datetime.utcnow() - timedelta(days=1)
        ]),
        "failed_count": len([j for j in all_jobs if j.status == DownloadJobStatus.failed]),
    }
    freeleech_jobs = [
        job
        for job in active_jobs
        if job.release and job.release.indexerFlags and "freeleech" in job.release.indexerFlags
    ]
    ratio_progress = 100
    if settings.ratio_goal > 0:
        ratio_progress = min(100, max(0, (settings.user_ratio / settings.ratio_goal) * 100))

    context = get_base_context(request, settings)
    context.update({
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "stats": stats,
        "seed_target_hours": settings.seed_target_hours,
        "freeleech_jobs": freeleech_jobs,
        "ratio_progress": ratio_progress,
    })

    return templates.TemplateResponse("mamlarr/dashboard.html", context)


@router.get("/fragments/active", response_class=HTMLResponse, name="active_fragment")
async def active_downloads_fragment(request: Request):
    """HTMX fragment: Active downloads (auto-refreshed)"""
    app = request.app
    settings: MamServiceSettings = app.state.settings
    job_store = app.state.job_store

    all_jobs = await job_store.list_all()
    active_jobs = [
        job
        for job in all_jobs
        if job.status in [DownloadJobStatus.downloading, DownloadJobStatus.seeding]
    ]

    context = get_base_context(request, settings)
    context.update({
        "active_jobs": active_jobs,
        "seed_target_hours": settings.seed_target_hours,
    })

    return templates.TemplateResponse("mamlarr/fragments/active_downloads.html", context)


@router.get("/jobs", response_class=HTMLResponse, name="jobs_list")
async def jobs_list(
    request: Request,
    status: Optional[str] = None,
):
    """Jobs list with filtering"""
    app = request.app
    settings: MamServiceSettings = app.state.settings
    job_store = app.state.job_store

    all_jobs = await job_store.list_all()

    # Filter by status if provided
    if status:
        all_jobs = [j for j in all_jobs if j.status == status]

    # Sort by created date, newest first
    all_jobs.sort(key=lambda j: j.created_at, reverse=True)

    context = get_base_context(request, settings)
    context.update({
        "jobs": all_jobs,
        "status_filter": status,
        "seed_target_hours": settings.seed_target_hours,
    })

    return templates.TemplateResponse("mamlarr/jobs.html", context)


@router.get("/jobs/{job_id}", response_class=HTMLResponse, name="job_detail")
async def job_detail(request: Request, job_id: str):
    """Detailed job view"""
    app = request.app
    settings: MamServiceSettings = app.state.settings
    job_store = app.state.job_store

    job = await job_store.get(job_id)

    if not job:
        # TODO: Return 404 page
        context = get_base_context(request, settings)
        context.update({"error": "Job not found"})
        return templates.TemplateResponse("mamlarr/error.html", context, status_code=404)

    # Get torrent info if available
    torrent_info = None
    if job.transmission_hash and app.state.manager:
        try:
            torrent_map = await app.state.manager.transmission.get_torrents([job.transmission_hash])
            torrent_info = torrent_map.get(job.transmission_hash)
        except Exception as e:
            logger.error("Failed to fetch torrent info", error=str(e))

    context = get_base_context(request, settings)
    context.update({
        "job": job,
        "torrent_info": torrent_info,
        "seed_target_hours": settings.seed_target_hours,
    })

    return templates.TemplateResponse("mamlarr/job_detail.html", context)


@router.get("/settings", response_class=HTMLResponse, name="settings")
async def settings_page(request: Request):
    """Mamlarr settings page"""
    app = request.app
    settings: MamServiceSettings = app.state.settings

    # Convert settings to dict for template
    config = {
        "api_key": settings.api_key,
        "mam_session_id": settings.mam_session_id,
        "mam_base_url": settings.mam_base_url,
        "transmission_url": settings.transmission_url,
        "transmission_username": settings.transmission_username,
        "transmission_password": settings.transmission_password,
        "qbittorrent_url": settings.qbittorrent_url,
        "qbittorrent_username": settings.qbittorrent_username,
        "qbittorrent_password": settings.qbittorrent_password,
        "qbittorrent_category": settings.qbittorrent_category,
        "qbittorrent_post_import_category": settings.qbittorrent_post_import_category,
        "qbittorrent_initial_state": settings.qbittorrent_initial_state.value,
        "qbittorrent_sequential": settings.qbittorrent_sequential,
        "qbittorrent_content_layout": settings.qbittorrent_content_layout.value,
        "qbittorrent_seed_ratio": settings.qbittorrent_seed_ratio,
        "qbittorrent_seed_time": settings.qbittorrent_seed_time,
        "seed_target_hours": settings.seed_target_hours,
        "download_directory": str(settings.download_directory),
        "enable_audio_merge": settings.enable_audio_merge,
        "remove_torrent_after_processing": settings.remove_torrent_after_processing,
        "use_mock_data": settings.use_mock_data,
        "user_ratio": settings.user_ratio,
        "ratio_goal": settings.ratio_goal,
        "bonus_points": settings.bonus_points,
        "freeleech_alerts_enabled": settings.freeleech_alerts_enabled,
        "use_transmission": settings.use_transmission,
        "use_qbittorrent": settings.use_qbittorrent,
    }

    context = get_base_context(request, settings)
    context.update({"config": config})

    return templates.TemplateResponse("mamlarr/settings.html", context)


def create_ui_router(settings: MamServiceSettings) -> APIRouter:
    """Factory to create UI router with settings"""
    return router
