# Mamlarr UI Integration Plan

## Overview

This document outlines how to build a UI for mamlarr that matches AudioBookRequest's look and feel while remaining completely separate to avoid merge conflicts with upstream.

## Tech Stack Analysis

AudioBookRequest uses:
- **Backend**: FastAPI with Jinja2 templates
- **CSS Framework**: Tailwind CSS + DaisyUI components
- **JavaScript**: HTMX (for dynamic content) + Alpine.js (for interactivity)
- **Themes**: Nord (light) and Night (dark) with auto theme switching
- **Layout Pattern**: Base template with navbar, centered content, responsive design

### Key DaisyUI Components Used
- `btn`, `btn-primary`, `btn-ghost`, `btn-square` - Buttons
- `card` - Card containers
- `table`, `table-zebra`, `table-pin-rows` - Tables
- `tabs`, `tab`, `tab-active` - Tab navigation
- `input`, `select` - Form elements
- `badge`, `badge-secondary` - Badges
- `join`, `join-item` - Joined elements (input + button)
- `navbar` - Navigation bar
- `modal`, `modal-box` - Modals

## Architecture: Keep It Separate

### Goals
1. ✅ Match AudioBookRequest's visual design exactly
2. ✅ Keep code completely separate for easy upstream merges
3. ✅ Run in same Docker container but maintain independence
4. ✅ Eventually add subtle integration points (navbar link, settings tab)

### Strategy: Standalone UI Service

```
Docker Container:
├── AudioBookRequest (main app on /)
│   └── Unmodified upstream code
└── Mamlarr (/mamlarr/*)
    ├── FastAPI app with UI routes
    ├── Own Jinja2 templates (copying style)
    ├── Reuse AudioBookRequest's static files
    └── API endpoints (/mamlarr/api/*)
```

## UI Pages to Build

### 1. Downloads Dashboard (`/mamlarr/`)
**Purpose**: Main page showing active downloads and recent activity

**Layout**:
```
┌─────────────────────────────────────────────────┐
│ Mamlarr - Download Manager                      │
│                                                  │
│ ┌─────────────────────────────────────────────┐ │
│ │ Active Downloads (3)                        │ │
│ │                                             │ │
│ │ ┌─────────────────────────────────────────┐ │ │
│ │ │ Foundation by Isaac Asimov              │ │ │
│ │ │ Status: Seeding (48h / 72h required)    │ │ │
│ │ │ [████████░░] 80% ratio: 1.2             │ │ │
│ │ │ Size: 450 MB | ↑ 2.1 MB/s | ↓ 0 MB/s   │ │ │
│ │ └─────────────────────────────────────────┘ │ │
│ │                                             │ │
│ │ [2 more active downloads...]               │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ ┌─────────────────────────────────────────────┐ │
│ │ Completed (Last 10)                        │ │
│ │ ✓ The Expanse - Downloaded & Processed     │ │
│ │ ✓ Project Hail Mary - Downloaded           │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**Features**:
- Live updates via HTMX polling
- Status badges (downloading/seeding/processing/completed/failed)
- Progress bars for download and seeding
- Ratio tracking
- Quick actions (pause, remove, force process)

### 2. Jobs/Torrents List (`/mamlarr/jobs`)
**Purpose**: Detailed table of all jobs with filtering

**Table Columns**:
- Title
- Status (badge)
- Progress (bar)
- Seed Time / Required
- Ratio
- Size
- Added Date
- Actions

**Filters**:
- Status: All, Active, Seeding, Completed, Failed
- Date range picker
- Search by title

### 3. Job Details (`/mamlarr/jobs/{job_id}`)
**Purpose**: Detailed view of a single job

**Sections**:
- **Job Info**: Title, GUID, status, timestamps
- **Torrent Details**: Hash, tracker, files list
- **Transmission Status**: Download/upload speeds, peers, ratio
- **Seeding Progress**: Time tracker with visual timeline
- **Processing Log**: Steps taken, any errors
- **Actions**: Force process, remove, re-download

### 4. Settings (`/mamlarr/settings`)
**Purpose**: Configure mamlarr service

**Settings Sections**:
- **MyAnonymouse**: Session cookie, base URL
- **Transmission**: RPC URL, credentials
- **Seeding Rules**: Target hours, ratio requirements
- **Post-Processing**: Audio merge toggle, output directory
- **Advanced**: API key, mock mode, debug options

### 5. Statistics (`/mamlarr/stats`) [Future]
**Purpose**: Analytics dashboard

**Metrics**:
- Total downloaded
- Current ratio
- Active torrents
- Seeding hours accumulated
- Processing success rate
- Storage used

## Component Design

### Status Badge Component
```html
<!-- templates/mamlarr/components/status_badge.html -->
{% if status == "downloading" %}
  <span class="badge badge-info">Downloading</span>
{% elif status == "seeding" %}
  <span class="badge badge-warning">Seeding</span>
{% elif status == "completed" %}
  <span class="badge badge-success">Completed</span>
{% elif status == "failed" %}
  <span class="badge badge-error">Failed</span>
{% else %}
  <span class="badge badge-ghost">{{ status }}</span>
{% endif %}
```

### Progress Bar Component
```html
<!-- templates/mamlarr/components/progress_bar.html -->
<div class="w-full">
  <div class="flex justify-between text-sm mb-1">
    <span>{{ label }}</span>
    <span>{{ progress }}%</span>
  </div>
  <progress class="progress {% if progress >= 100 %}progress-success{% elif progress >= 50 %}progress-warning{% else %}progress-info{% endif %}"
            value="{{ progress }}"
            max="100"></progress>
</div>
```

### Job Card Component
```html
<!-- templates/mamlarr/components/job_card.html -->
<div class="card bg-base-200 shadow-md">
  <div class="card-body">
    <div class="flex justify-between items-start">
      <h3 class="card-title text-lg">{{ job.release.title }}</h3>
      {% include "mamlarr/components/status_badge.html" %}
    </div>

    <div class="space-y-2 mt-2">
      <!-- Download Progress -->
      {% if job.status in ["downloading", "seeding"] %}
        {% include "mamlarr/components/progress_bar.html" with label="Download" progress=job.download_percent %}
      {% endif %}

      <!-- Seeding Progress -->
      {% if job.status == "seeding" %}
        <div class="text-sm opacity-70">
          Seeding: {{ job.seed_hours }}h / {{ required_hours }}h
          | Ratio: {{ job.ratio|round(2) }}
        </div>
        {% include "mamlarr/components/progress_bar.html" with label="Seeding Time" progress=job.seed_percent %}
      {% endif %}

      <!-- Stats -->
      <div class="flex gap-4 text-sm opacity-70">
        <span>{{ job.size_mb }} MB</span>
        {% if job.status in ["downloading", "seeding"] %}
          <span>↑ {{ job.upload_speed }}</span>
          <span>↓ {{ job.download_speed }}</span>
        {% endif %}
      </div>
    </div>

    <div class="card-actions justify-end mt-2">
      <a href="/mamlarr/jobs/{{ job.id }}" class="btn btn-sm btn-ghost">Details</a>
    </div>
  </div>
</div>
```

## File Structure

```
mamlarr/
├── mamlarr_service/
│   ├── api.py              # Existing API routes
│   ├── ui.py               # NEW: UI routes serving templates
│   ├── ui_helpers.py       # NEW: Helper functions for UI data
│   └── ...existing files...
├── templates/              # NEW: Mamlarr templates
│   └── mamlarr/
│       ├── base.html       # Base template (mimics AudioBookRequest)
│       ├── dashboard.html  # Main downloads dashboard
│       ├── jobs.html       # Jobs list table
│       ├── job_detail.html # Single job detail view
│       ├── settings.html   # Mamlarr settings
│       ├── components/
│       │   ├── status_badge.html
│       │   ├── progress_bar.html
│       │   ├── job_card.html
│       │   └── job_table_row.html
│       └── fragments/      # HTMX partial templates
│           ├── active_downloads.html
│           ├── completed_jobs.html
│           └── job_status.html
└── static/                 # Reuse AudioBookRequest's static files
```

## FastAPI Routes Structure

### UI Routes (in `mamlarr_service/ui.py`)
```python
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/mamlarr", tags=["ui"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard showing active downloads"""
    active_jobs = await get_active_jobs()
    completed_jobs = await get_recent_completed_jobs(limit=10)
    stats = await get_stats_summary()
    return templates.TemplateResponse("mamlarr/dashboard.html", {
        "request": request,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "stats": stats,
    })

@router.get("/jobs", response_class=HTMLResponse)
async def jobs_list(request: Request, status: str = None):
    """Jobs list with filtering"""
    jobs = await get_jobs(status_filter=status)
    return templates.TemplateResponse("mamlarr/jobs.html", {
        "request": request,
        "jobs": jobs,
        "status_filter": status,
    })

@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    """Detailed job view"""
    job = await get_job(job_id)
    torrent_info = await get_torrent_info(job.transmission_hash)
    return templates.TemplateResponse("mamlarr/job_detail.html", {
        "request": request,
        "job": job,
        "torrent_info": torrent_info,
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Mamlarr settings page"""
    config = await load_mamlarr_config()
    return templates.TemplateResponse("mamlarr/settings.html", {
        "request": request,
        "config": config,
    })

# HTMX Fragment endpoints for live updates
@router.get("/fragments/active", response_class=HTMLResponse)
async def active_downloads_fragment(request: Request):
    """Partial template for active downloads (polled by HTMX)"""
    active_jobs = await get_active_jobs()
    return templates.TemplateResponse("mamlarr/fragments/active_downloads.html", {
        "request": request,
        "active_jobs": active_jobs,
    })
```

## Integration Points (Non-Invasive)

### Option 1: Navbar Link (Minimal Modification)
Add a single link to AudioBookRequest's navbar (easy to maintain):

```html
<!-- In templates/base.html, add one line -->
<a href="{{ base_url }}/mamlarr/" class="btn btn-ghost btn-square" title="Downloads">
  {% include "icons/download.html" %}
</a>
```

### Option 2: Settings Tab (Slightly More Invasive)
Add mamlarr tab to settings tabs:

```html
<!-- In templates/settings_page/base.html -->
<a preload href="{{ base_url }}/mamlarr/settings" role="tab"
  class="tab {% if page=='mamlarr' %}tab-active{% endif %}">Mamlarr</a>
```

### Option 3: Standalone (Zero Modification)
Keep mamlarr completely standalone:
- Users access via `/mamlarr/` directly
- No changes to AudioBookRequest templates
- Can be documented in README

**Recommendation**: Start with Option 3, then add Option 1 link once stable.

## HTMX Live Updates

Use HTMX polling for real-time updates:

```html
<!-- Active downloads section that auto-refreshes -->
<div hx-get="/mamlarr/fragments/active"
     hx-trigger="every 5s"
     hx-swap="outerHTML">
  <!-- Initial content, replaced every 5 seconds -->
  {% include "mamlarr/fragments/active_downloads.html" %}
</div>
```

## Theme Integration

Mamlarr templates should use the same theme system:

```html
<!DOCTYPE html>
<html lang="en" data-theme="nord">
<head>
  <meta charset="UTF-8">
  <title>Mamlarr - {{ page_title }}</title>

  <!-- Reuse AudioBookRequest's CSS -->
  <link rel="stylesheet" href="{{ base_url }}/static/globals.css?v={{ version }}">

  <!-- Reuse AudioBookRequest's JS -->
  <script src="{{ base_url }}/static/htmx.js?v={{ version }}"></script>
  <script defer src="{{ base_url }}/static/htmx-preload.js?v={{ version }}"></script>
  <script src="{{ base_url }}/static/alpine.js?v={{ version }}" defer></script>

  <!-- Theme switching (same as AudioBookRequest) -->
  <script>
    const setTheme = /* ...same code as AudioBookRequest... */
    setTheme();
  </script>
</head>
<body class="w-screen min-h-screen overflow-x-hidden" hx-ext="preload">
  <!-- Content -->
</body>
</html>
```

## Docker Integration

### Single Container Setup

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install both apps
COPY app/ /app/app/
COPY mamlarr/ /app/mamlarr/

# Install dependencies
RUN pip install -e /app/
RUN pip install -e /app/mamlarr/

# Copy templates (mamlarr templates go in their own folder)
COPY templates/ /app/templates/
COPY mamlarr/templates/ /app/mamlarr/templates/

# Shared static files
COPY static/ /app/static/

# Startup script that runs both services
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
```

### Startup Script

```bash
#!/bin/bash
# start.sh - Run both AudioBookRequest and Mamlarr

# Start AudioBookRequest on port 5000
uvicorn app.main:app --host 0.0.0.0 --port 5000 &

# Start Mamlarr on port 8000
uvicorn mamlarr_service.main:app --host 0.0.0.0 --port 8000 &

# Use nginx or another reverse proxy to route:
# / -> AudioBookRequest (port 5000)
# /mamlarr/* -> Mamlarr (port 8000)

# Or mount mamlarr into AudioBookRequest's FastAPI app
wait
```

### Alternative: Mount Mamlarr in AudioBookRequest

```python
# In AudioBookRequest's main.py (minimal change)
from mamlarr_service.ui import router as mamlarr_router

app.include_router(mamlarr_router)  # Mounts all /mamlarr/* routes
```

This way, both run in a single FastAPI app, single process.

## Development Workflow

1. **Phase 1: Build Standalone UI**
   - Create templates matching AudioBookRequest style
   - Add UI routes to mamlarr
   - Test locally at `http://localhost:8000/mamlarr/`

2. **Phase 2: Docker Integration**
   - Update Dockerfile to include mamlarr
   - Test both services in container
   - Verify theme and static files work

3. **Phase 3: Optional Link Integration**
   - Add navbar link (1-line change)
   - Document the change for upstream merges
   - Or keep completely standalone

4. **Phase 4: Enhanced Features**
   - Add live notifications (when download completes)
   - Add quick-add from AudioBookRequest search results
   - Add MAM tracker integration features

## Future Enhancement Ideas

### Integration with AudioBookRequest
- **Quick Download from Search**: Add "Download with Mamlarr" button in search results
- **Status in Wishlist**: Show mamlarr download status next to books
- **Notifications**: Integrate with AudioBookRequest's notification system
- **Shared Database**: Track which books were downloaded via mamlarr

### Advanced MAM Features
- **Freeleech Alerts**: Notify when freeleech books appear
- **VIP Tracking**: Show VIP status and perks
- **Bonus Points**: Display and manage MAM bonus points
- **Upload Tracking**: Show contribution stats
- **Ratio Monitoring**: Alerts when ratio drops below threshold

### Enhanced Download Manager
- **Priority Queue**: Reorder downloads by priority
- **Bandwidth Limits**: Set global upload/download limits
- **Scheduler**: Only seed during certain hours
- **Auto-Remove**: Remove torrents after X days past requirement
- **Storage Alerts**: Warn when disk space is low

## Summary

This plan provides:
- ✅ Complete visual consistency with AudioBookRequest
- ✅ Zero or minimal modification to upstream code
- ✅ Easy Docker integration
- ✅ Foundation for future enhancements
- ✅ Clean separation of concerns

The key principle: **Build mamlarr UI as a standalone component that happens to look exactly like AudioBookRequest, making it feel like a natural extension rather than a separate app.**
