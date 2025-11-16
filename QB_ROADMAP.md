# qBittorrent Integration Roadmap

Goal: Add qBittorrent as a first-class download provider alongside Transmission while keeping the end-user experience identical.

## Phase 1 – Configuration & UX
1. Add qBittorrent settings to the UI/`.env`:
   - `MAM_SERVICE_QBITTORRENT_URL`
   - `MAM_SERVICE_QBITTORRENT_USERNAME`
   - `MAM_SERVICE_QBITTORRENT_PASSWORD`
2. Extend the settings page to show Transmission and qBittorrent blocks, each with an “Enable” toggle (radio-button behaviour so only one can be active at a time).
3. Update `/mamlarr/api/settings/*` handlers to persist the qB credentials and enforce “exactly one provider enabled” (return 400 if both true/false).
4. Update “Test Connection” HTMX button to call Transmission or qB test endpoint based on the active provider.

## Phase 2 – qBittorrent Client
1. Implement `QbitClient` mirroring TransmissionClient API:
   - `login` (POST `/api/v2/auth/login`)
   - `add_torrent` (POST `/api/v2/torrents/add`)
   - `get_torrents` → returns progress/seed info
   - `remove_torrent`
   - `test_connection`
2. Reuse the shared aiohttp session and add cookie handling for qB auth token.

## Phase 3 – Download Manager Abstraction
1. Introduce a provider abstraction (e.g., `BaseTorrentClient` with `add`, `get_status`, `remove`, `test_connection`).
2. Update `DownloadManager` to instantiate the appropriate client (Transmission or qB) during `_restart_manager`.
3. Ensure seeding tracking, job statuses, and error logging work identically regardless of provider.

## Phase 4 – UI Enhancements
1. Surface which provider is active on the dashboard (icon/badge).
2. Add provider-specific notes (e.g., qB’s need for `/api/v2` base path) in the settings helper text.
3. Update docs (README + DOCKER_SETUP) with qB instructions and environment variables.

## Phase 5 – Testing & Rollout
1. Add unit tests for the qB client (mock HTTP responses).
2. Extend e2e/mock tests to cover provider switching (Transmission → qB).
3. Validate Docker build includes optional qB dependencies (none needed beyond aiohttp).

Deliverables per phase can be split into separate PRs. Start with Phase 1 (config + UI radio toggle) before wiring the backend.
