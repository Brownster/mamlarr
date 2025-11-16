# Mamlarr (MyAnonamouse Download Service)

Mamlarr is a Prowlarr-compatible shim that lets AudioBookRequest (or any other client) search MyAnonamouse, trigger Transmission downloads, enforce tracker rules (72h seeding, ratio guardrails, unsatisfied limits), and post-process finished audiobooks into `/mnt/storage/audiobooks/`.

## Quick Start

### Offline Testing (Recommended First)

Test mamlarr without needing real MyAnonymouse credentials:

```bash
cd mamlarr
uv sync                    # Install dependencies
./run_dev_server.sh        # Start in mock mode
```

Then visit http://localhost:8000/docs to see the API.

**For detailed testing instructions, see [OFFLINE_TESTING_SETUP.md](OFFLINE_TESTING_SETUP.md)**
<img width="1904" height="857" alt="image" src="https://github.com/user-attachments/assets/7b6d6e79-9d0d-4319-8d15-588f632b5db0" />

### Production Setup

```bash
cd mamlarr
uv sync  # Install dependencies
export MAM_SERVICE_API_KEY="supersecret"
export MAM_SERVICE_MAM_SESSION_ID="your_mam_cookie"
export MAM_SERVICE_TRANSMISSION_URL="https://tr-XX-XX-XX-XX.a.seedbox.vip:443/transmission/rpc"
export MAM_SERVICE_TRANSMISSION_USERNAME="seedbox_username"
export MAM_SERVICE_TRANSMISSION_PASSWORD="seedbox_password"
export MAM_SERVICE_QBITTORRENT_URL="https://seedbox:443/api/v2"
export MAM_SERVICE_QBITTORRENT_USERNAME="seedbox_username"
export MAM_SERVICE_QBITTORRENT_PASSWORD="seedbox_password"
export MAM_SERVICE_DOWNLOAD_DIRECTORY="/mnt/storage/audiobooks"
export MAM_SERVICE_SEARCH_TYPE="all"
export MAM_SERVICE_SEARCH_IN_DESCRIPTION="false"
export MAM_SERVICE_SEARCH_IN_SERIES="true"
export MAM_SERVICE_SEARCH_IN_FILENAMES="false"
export MAM_SERVICE_SEARCH_LANGUAGES=""  # comma-separated language IDs

uvicorn mamlarr_service.api:app --host 0.0.0.0 --port 8000
```

Point AudioBookRequest’s “Prowlarr” settings at this FastAPI instance and reuse the API key above. The search endpoint (`/api/v1/search`) now proxies MyAnonamouse search results, and POSTing the GUID to `/api/v1/search` queues a download job that:

1. Retrieves the `.torrent` from MAM using your authenticated session.
2. Sends it to Transmission through RPC.
3. Monitors the torrent until the seeding requirement (default 72 hours) is satisfied.
4. Runs post-processing to merge/copy the audiobook into the configured download directory.
5. Marks the job `completed`, optionally removing the torrent from Transmission.

See `ROADMAP.md` for the full implementation plan and outstanding work.

## Combined Docker with AudioBookRequest

To run AudioBookRequest and Mamlarr in a single container, use the provided Dockerfile + compose stack:

```bash
cd mamlarr
docker compose up --build
```

This builds both apps and exposes:

- AudioBookRequest → http://localhost:8000
- Mamlarr → http://localhost:8800/mamlarr/

CI integration: `.github/workflows/docker-build.yml` builds and pushes the image to GHCR (`ghcr.io/<owner>/abr-mamlarr:latest`) whenever `main/master` changes.

### MyAnonamouse session creation help

Jackett’s “Security Preferences → Session Creation” workflow is documented in [`docs/mam_setup.md`](docs/mam_setup.md). Follow those steps to mint a dedicated `mam_id` cookie, note the inactivity warning from MyAnonamouse, and paste the resulting value into `MAM_SERVICE_MAM_SESSION_ID` (or the UI settings page). The same instructions, plus the current search-filter defaults, are also available from the FastAPI [`GET /config`](#fastapi-config-helper) endpoint so UIs can surface them inline.

### FastAPI config helper

Mamlarr exposes a lightweight [`GET /config`](http://localhost:8000/config) endpoint that returns:

- The Jackett-style “security preferences → session creation” checklist.
- The inactivity warning text quoted by MyAnonamouse.
- Metadata for the search filter environment variables (`MAM_SERVICE_SEARCH_TYPE`, `MAM_SERVICE_SEARCH_IN_DESCRIPTION`, `MAM_SERVICE_SEARCH_IN_SERIES`, `MAM_SERVICE_SEARCH_IN_FILENAMES`, `MAM_SERVICE_SEARCH_LANGUAGES`).

That JSON payload gives downstream dashboards (AudioBookRequest, the standalone UI, etc.) everything they need to show the same instructions documented above.
