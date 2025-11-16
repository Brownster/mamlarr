# Mamlarr Web UI - Complete Guide

## 🎉 What You Now Have

A **complete web interface** for mamlarr that looks **exactly like AudioBookRequest** but is kept completely separate for easy upstream merges. The UI is production-ready and includes:

### ✅ Pages Built
1. **Dashboard** (`/mamlarr/`) - Real-time download monitoring
2. **Jobs List** (`/mamlarr/jobs`) - Full history with filtering
3. **Settings** (`/mamlarr/settings`) - Configuration interface
4. **Live Updates** - HTMX polling every 5 seconds

### ✅ Features
- 📊 Stats cards (Active, Seeding, Completed, Failed)
- 🔄 Real-time progress bars and seeding trackers
- 🎨 Status badges with animated icons
- 📱 Fully responsive design
- 🌓 Light/dark theme support (Nord/Night)
- ⚡ Live updates via HTMX (no manual refresh)
- 🗑️ Quick actions (view details, remove torrents)

## Quick Start

### 1. Test the UI Now

```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
./run_dev_server.sh
```

Then visit:
- **Dashboard**: http://localhost:8000/mamlarr/
- **Jobs**: http://localhost:8000/mamlarr/jobs
- **Settings**: http://localhost:8000/mamlarr/settings
- **API Docs**: http://localhost:8000/docs

### 2. What You'll See

**Dashboard Page:**
```
┌─────────────────────────────────────────┐
│ Download Manager                        │
│ Manage your MyAnonymouse downloads      │
├─────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│ │Active│ │Seeding│ │ Done │ │Failed│   │
│ │  3   │ │  2   │ │  12  │ │  0   │   │
│ └──────┘ └──────┘ └──────┘ └──────┘   │
├─────────────────────────────────────────┤
│ ⟳ Active Downloads                     │
│ ┌─────────────────────────────────────┐ │
│ │ Foundation by Isaac Asimov          │ │
│ │ Status: Seeding                     │ │
│ │ [████████░░] 48h / 72h             │ │
│ │ 450 MB | ↑ 2.1 MB/s                │ │
│ │ [Details] [Remove]                  │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Docker Integration

You mentioned wanting both in one container. Here are your options:

### Option A: Mount Mamlarr in AudioBookRequest (Recommended)

```python
# In AudioBookRequest's main FastAPI file
from mamlarr_service.ui import router as mamlarr_router

app.include_router(mamlarr_router)  # Adds all /mamlarr/* routes
```

**Benefits:**
- Single process, single port
- Shared static files and templates
- Easy deployment
- No reverse proxy needed

### Option B: Separate Processes + Reverse Proxy

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install both apps
COPY app/ /app/app/
COPY mamlarr/ /app/mamlarr/
COPY templates/ /app/templates/
COPY static/ /app/static/

RUN pip install -e /app/
RUN pip install -e /app/mamlarr/

# Start script runs both
CMD ["/app/start.sh"]
```

```bash
#!/bin/bash
# start.sh
uvicorn app.main:app --host 0.0.0.0 --port 5000 &
uvicorn mamlarr_service.api:app --host 0.0.0.0 --port 8000 &
wait
```

Then use nginx to route:
- `/` → AudioBookRequest (port 5000)
- `/mamlarr/*` → Mamlarr (port 8000)

## Adding Navbar Link to AudioBookRequest

To make mamlarr accessible from AudioBookRequest's navbar, add this **single line** to `templates/base.html`:

```html
<!-- After the wishlist button, around line 167 -->
<a href="/mamlarr/" class="btn btn-ghost btn-square" title="Downloads">
  <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
  </svg>
</a>
```

**That's it!** Just one link. Easy to maintain during upstream merges.

## File Structure

```
mamlarr/
├── mamlarr_service/
│   ├── api.py           # API routes + UI integration
│   ├── ui.py            # NEW: UI routes
│   ├── settings.py      # Configuration
│   ├── models.py        # Data models
│   └── ...other files
├── templates/
│   └── mamlarr/
│       ├── base.html            # Base template
│       ├── dashboard.html       # Main dashboard
│       ├── jobs.html            # Jobs list
│       ├── settings.html        # Settings page
│       ├── components/          # Reusable components
│       │   ├── status_badge.html
│       │   ├── progress_bar.html
│       │   └── job_card.html
│       └── fragments/           # HTMX partials
│           └── active_downloads.html
└── pyproject.toml       # Updated with jinja2
```

## Tech Stack (Matches AudioBookRequest)

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Jinja2 templates |
| CSS | Tailwind CSS + DaisyUI |
| JavaScript | HTMX + Alpine.js |
| Themes | Nord (light) / Night (dark) |
| Icons | Heroicons (SVG) |
| Live Updates | HTMX polling |

## What Was Added

- ✅ **Settings API**: every form on `/mamlarr/settings` now hits real FastAPI handlers that persist changes to `data/settings.json`, update the running service, and restart the download manager when needed.
- ✅ **Job Detail Page**: `/mamlarr/jobs/:id` shows seeding progress, tracker badges (freeleech, VIP, etc.), ratio/bonus summaries, and destination paths.
- ✅ **Delete Jobs**: HTMX delete actions remove torrents (with a tracker warning) and drop the card inline.
- ✅ **Freeleech/Raio/Bonus Widgets**: dashboard now highlights freeleech downloads, ratio progress, and bonus point totals; settings expose toggles to manage alerts.

## Future Enhancements

### Phase 1: Core Functionality
- ✅ Dashboard UI
- ✅ Jobs list
- ✅ Settings UI
- ✅ Settings API (save config)
- ✅ Job detail page
- ✅ Delete/remove actions

### Phase 2: Integration
- Add "Download with Mamlarr" button in AudioBookRequest search
- Show mamlarr status in wishlist
- Shared notifications
- Single auth system

### Phase 3: Advanced Features
- Richer ratio trend charts & history
- Bandwidth limits
- Bandwidth limits
- Scheduling (seed only at night)
- Statistics dashboard

### Phase 4: MAM-Specific
- Live bonus points sync from tracker
- VIP status display
- Unsatisfied torrent alerts
- Upload tracking

## Design Principles

**"Build mamlarr UI as a standalone component that happens to look exactly like AudioBookRequest"**

✅ **Zero modification** to AudioBookRequest (except optional nav link)
✅ **Exact visual match** - uses same components and styling
✅ **Reuse assets** - shares CSS, JS, icons from AudioBookRequest
✅ **Easy merges** - completely separate codebase
✅ **Docker-ready** - can run in same container

## Testing

### Visual Test
```bash
./run_dev_server.sh
# Visit http://localhost:8000/mamlarr/
```

### Integration Test
1. Start AudioBookRequest
2. Mount mamlarr routes (or run separately)
3. Configure Prowlarr in AudioBookRequest → mamlarr
4. Search and download a book
5. Watch it appear in mamlarr dashboard

### Mock Data
In mock mode, you'll see fake downloads to test the UI without real trackers.

## Maintenance

### Keeping Up with AudioBookRequest Updates

Since mamlarr is separate:

```bash
# Update AudioBookRequest
cd /path/to/AudioBookRequest
git pull upstream main

# No conflicts! Mamlarr is in mamlarr/ folder
```

Only the navbar link (if you add it) needs to be tracked:

```markdown
# CUSTOMIZATION LOG
File: templates/base.html
Line: ~167
Change: Added mamlarr link to navbar
Can be safely removed or updated during merges
```

## Documentation

- **[UI_INTEGRATION_PLAN.md](UI_INTEGRATION_PLAN.md)** - Complete technical design
- **[UI_COMPLETE.md](UI_COMPLETE.md)** - Implementation details
- **[TESTING.md](TESTING.md)** - How to test offline
- **[OFFLINE_TESTING_SETUP.md](OFFLINE_TESTING_SETUP.md)** - Setup guide
- **This file** - User guide

## Troubleshooting

### "Module not found" error
```bash
cd mamlarr
uv sync  # Installs jinja2 and other deps
```

### Templates not found
Make sure templates are in `mamlarr/templates/mamlarr/`

### CSS not loading
Templates reference `{{ base_url }}/static/...` which should point to AudioBookRequest's static files

### Port conflicts
```bash
# Change port in run_dev_server.sh
uvicorn mamlarr_service.api:app --reload --port 8002
```

## Summary

🎉 **You now have a complete, production-ready UI for mamlarr!**

✅ Matches AudioBookRequest's design perfectly
✅ Completely separate codebase (easy merges)
✅ Live-updating dashboard
✅ Responsive + themed
✅ Docker-ready
✅ Easy to maintain

**Next steps:**
1. Test it: `./run_dev_server.sh`
2. Decide on Docker approach (Option A or B)
3. Implement settings API endpoints
4. Add navbar link (optional)
5. Deploy and enjoy!

The UI is ready to use right now. Just run the dev server and navigate to `/mamlarr/` 🚀
