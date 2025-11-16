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

### Production Setup

```bash
cd mamlarr
uv sync  # Install dependencies
export MAM_SERVICE_API_KEY="supersecret"
export MAM_SERVICE_MAM_SESSION_ID="your_mam_cookie"
export MAM_SERVICE_TRANSMISSION_URL="http://seedbox:9091/transmission/rpc"
export MAM_SERVICE_TRANSMISSION_USERNAME="transmission"
export MAM_SERVICE_TRANSMISSION_PASSWORD="password"
export MAM_SERVICE_DOWNLOAD_DIRECTORY="/mnt/storage/audiobooks"

uvicorn mamlarr_service.api:app --host 0.0.0.0 --port 8000
```

Point AudioBookRequest’s “Prowlarr” settings at this FastAPI instance and reuse the API key above. The search endpoint (`/api/v1/search`) now proxies MyAnonamouse search results, and POSTing the GUID to `/api/v1/search` queues a download job that:

1. Retrieves the `.torrent` from MAM using your authenticated session.
2. Sends it to Transmission through RPC.
3. Monitors the torrent until the seeding requirement (default 72 hours) is satisfied.
4. Runs post-processing to merge/copy the audiobook into the configured download directory.
5. Marks the job `completed`, optionally removing the torrent from Transmission.

See `ROADMAP.md` for the full implementation plan and outstanding work.
