# MyAnonamouse Download Service Roadmap

## Overview
- **Purpose:** Build a Prowlarr-compatible download service that searches MyAnonamouse, manages torrent lifecycles through Transmission, performs audiobook post-processing, and deposits final files into `/mnt/storage/audiobooks/` for AudiobookShelf imports.
- **Scope:** Standalone service with a small API that AudioBookRequest can treat as “Prowlarr”, plus background workers that maintain tracker compliance (ratios, seed times) and enforce MyAnonamouse rules.

## Goals & Constraints
1. Provide `/api/v1/search` and `/api/v1/release/push` endpoints that mirror Prowlarr so AudioBookRequest works unchanged.
2. Authenticate with MyAnonamouse (cookie/session) to perform searches and authenticated torrent downloads.
3. Use Transmission RPC to add torrents to the seedbox, monitor progress, and keep seeding per tracker requirements (e.g., seed ≥72 hours or ratio ≥1.0—adjust once exact rules are confirmed).
4. Post-process completed downloads: consolidate multi-file releases (e.g., merge chapters into a single M4B via `ffmpeg`/`m4b-tool`), embed metadata if possible, and place the finished audiobook into `/mnt/storage/audiobooks/`.
5. Track every job in persistent storage (DB or durable KV) for observability, retries, and enforcement of seeding rules.
6. Design for eventual multi-tracker support, but optimize the first version for MAM.

### Tracker Compliance Requirements (MyAnonamouse)
- Keep torrents seeding for at least **72 hours within 30 days** after completion (Rule 2.5). Track accrued seeding time even across restarts so the automation does not stop early.
- Maintain **global ratio ≥ 1.0** (Rule 2.4). Expose alerts/pauses if automation risks dropping below ratio due to large downloads.
- Respect the **unsatisfied torrent limits** (Rule 2.8) based on account class (20/50/100/150/200). The service should throttle concurrent grabs to stay under the ceiling.
- **No partial downloads** (Rule 2.7). Always download the full torrent payload before processing.
- Use only **approved clients** (Rule 2.3). For Transmission, stick to 2.94 or 4.0.1–4.0.x and disable auto-updates so the fingerprint stays valid.
- Preserve `.torrent` files privately (Rule 2.2). If sharing elsewhere, regenerate torrents (out of scope here but worth documenting).
- Continue seeding even when nobody is leeching to accumulate Karma points (Rule 2.1). Automation should avoid stopping torrents once minimums are reached unless storage pressure forces it.
- Ensure new accounts respect the **initial 10 GB upload-credit buffer** (Rule 2.6) by staging smaller downloads until ratio improves.

## Architecture Outline
- **API Layer:** FastAPI app exposing minimal Prowlarr-compatible routes. Handles auth via API key and orchestrates search/download requests.
- **Indexer Adapter (MyAnonamouse):** Module reusing logic similar to `MamIndexer` to issue JSON search requests, parse results, and fetch torrent files while respecting rate limits.
- **Torrent Manager:** Transmission RPC client that creates torrents, polls status, enforces seeding minimums, and triggers post-processing when allowed to stop.
- **Job Store:** Database tables (e.g., SQLite/Postgres via SQLModel) tracking requests, torrent IDs, current state (queued/downloading/seeding/processing/done), error logs, and seed timers.
- **Post-Processor:** Background worker that watches for completed torrents, runs conversion/merging scripts, validates output, and moves files into `/mnt/storage/audiobooks/`.
- **Integration Adapter:** Small client so AudioBookRequest can ping this service instead of real Prowlarr (same URL + API key fields).

## Phased Roadmap
### Phase 1: Foundations
- Decide runtime (FastAPI + SQLModel + APScheduler).
- Define DB schema for jobs, torrents, processing tasks.
- Implement Prowlarr-compatible API skeleton with mocked responses.

### Phase 2: MyAnonamouse Search Integration
- Port `MamIndexer` search logic and session handling.
- Map search results into Prowlarr release schema (title, infoUrl, guid, size, seeders, etc.).
- Add configuration management for session ID refresh and rate limiting.

### Phase 3: Torrent Lifecycle Management
- Implement Transmission RPC client wrapper (add torrent, get status, set stop conditions).
- Handle `/release/push`: download torrent file/magnet via MAM, add to Transmission, create job records.
- Build background worker that polls torrents, updates job state, and enforces seeding commitments (track elapsed time/ratio; pause/remove torrent only when compliant).

### Phase 4: Post-Processing & Delivery
- Define conversion pipeline (e.g., `ffmpeg`/`m4b-tool`) to merge multi-file releases, normalize formats, and embed metadata when available.
- Implement file mover that transfers finished audiobooks into `/mnt/storage/audiobooks/` atomically (temp directory → final path) and logs outcomes.
- Expose job status API/UI to inspect progress and failures.

### Phase 5: Integration & Hardening
- Point AudioBookRequest’s Prowlarr config at the new service and run end-to-end tests (request → search → download → seed → process → AudiobookShelf pickup).
- Add alerting/logging for MAM errors, Transmission failures, or post-processing issues.
- Document operational runbooks (refreshing MAM cookies, clearing stuck torrents, cleaning staging directories).
- Evaluate multi-tracker extensibility and seeding strategies for other private trackers.

## Risks & Mitigations
- **Tracker Compliance:** Automate seed timers/ratio checks and consider scripting Transmission groups so MAM torrents stay active until compliant.
- **Session Expiry:** Provide health checks and alerts when MAM session IDs expire; optionally implement auto-login if TOTP/API tokens are available.
- **Post-Processing Failures:** Run conversions in isolated workspaces, validate outputs before moving, and keep raw downloads until success.
- **Storage Pressure:** Monitor `/mnt/storage/audiobooks/` and seedbox disk usage; consider pruning policies once seeding obligations end.

## Next Steps
1. Confirm MyAnonamouse rule specifics (exact seed ratios/times) and document them in the service config.
2. Scaffold the FastAPI service + DB migrations.
3. Build the search endpoint end-to-end, then iterate through the phases above.
