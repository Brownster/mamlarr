# Mamlarr Offline Testing Setup - Complete Guide

## What Was Created

I've set up a complete offline testing environment for your mamlarr Prowlarr-compatible service. Here's what was added:

### Configuration Files
- **`pyproject.toml`** - Package definition with all dependencies (FastAPI, aiohttp, pydantic, etc.)
- Dependencies are now installed with `uv sync`

### Testing Scripts

1. **`run_dev_server.sh`** - Start mamlarr in pure mock mode (fastest)
   - No external services needed
   - Uses in-memory mocks for everything
   - Perfect for basic API testing

2. **`test_with_mock_tracker.sh`** - Start with mock MAM + Transmission server
   - More realistic testing
   - Simulates actual HTTP calls to MyAnonymouse
   - Includes Transmission RPC simulation

3. **`test_api.sh`** - Quick curl-based API tests
   - Tests all endpoints manually
   - Good for debugging

4. **`quick_test.py`** - Python validation script
   - Verifies the service can start
   - Lists all available routes

### Documentation
- **`TESTING.md`** - Comprehensive testing guide
- **`OFFLINE_TESTING_SETUP.md`** - This file

## Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
uv sync
```

### Step 2: Run the Service
```bash
./run_dev_server.sh
```

The service will start at `http://localhost:8000` with API key `dev-test-key`.

### Step 3: Test It
Open another terminal and run:
```bash
./test_api.sh
```

Or visit in your browser:
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Integration with AudioBookRequest

Once the mamlarr service is running, configure AudioBookRequest:

1. Go to AudioBookRequest's Prowlarr settings
2. Set:
   - **Base URL**: `http://localhost:8000`
   - **API Key**: `dev-test-key`
3. Test the connection - it should see "MyAnonamouse" indexer
4. Search for audiobooks in AudioBookRequest - searches will go through mamlarr

## How Mock Mode Works

Mamlarr has two testing modes:

### Mode 1: Pure Mock (Default in `run_dev_server.sh`)
```
AudioBookRequest → Mamlarr API → In-memory mocks → Fake files in ./output/
```

**What it simulates:**
- ✓ Prowlarr-compatible API endpoints
- ✓ Mock search results (1 fake audiobook)
- ✓ Mock torrent download
- ✓ Mock Transmission client (in-memory)
- ✓ Mock file processing
- ✓ Job tracking

**Environment variables used:**
```bash
MAM_SERVICE_USE_MOCK_DATA="true"
MAM_SERVICE_SEED_TARGET_HOURS="0"  # Skip seeding delay
MAM_SERVICE_ENABLE_AUDIO_MERGE="false"  # Simple file copy
```

### Mode 2: Mock Tracker (Via `test_with_mock_tracker.sh`)
```
AudioBookRequest → Mamlarr API → Mock HTTP Server → Fake MAM/Transmission responses
```

**What it simulates:**
- ✓ Everything from Mode 1
- ✓ Actual HTTP requests to mock MAM API
- ✓ Actual HTTP requests to mock Transmission RPC
- ✓ More realistic network behavior

**Services started:**
- Port 8001: Mock tracker (MAM + Transmission)
- Port 8000: Mamlarr API

## Testing Checklist

Run through these tests to validate everything works:

### Basic API Tests
- [ ] Health check works: `curl http://localhost:8000/health`
- [ ] Indexers endpoint returns MyAnonymouse
- [ ] Search returns mock results
- [ ] Download creates a job
- [ ] Job status can be queried

### Integration Tests
- [ ] AudioBookRequest can connect to mamlarr as Prowlarr
- [ ] Searches from AudioBookRequest return results
- [ ] Can trigger downloads from AudioBookRequest
- [ ] Files appear in `./output/` directory

### Workflow Tests
- [ ] Mock download completes immediately (seed_target_hours=0)
- [ ] Post-processing creates output file
- [ ] Job status shows "completed"

## Common Issues & Solutions

### Issue: "Module not found" errors
**Solution:**
```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
uv sync
```

### Issue: "Port 8000 already in use"
**Solution:** Either:
1. Kill existing process: `lsof -ti:8000 | xargs kill`
2. Or change port in script: Edit `run_dev_server.sh` and change `--port 8000` to `--port 8002`

### Issue: "Permission denied" when running scripts
**Solution:**
```bash
chmod +x run_dev_server.sh test_with_mock_tracker.sh test_api.sh quick_test.py
```

### Issue: Downloads not completing
**Check:**
1. Is `MAM_SERVICE_SEED_TARGET_HOURS` set to `0`?
2. Does the output directory exist? `mkdir -p output/tmp`
3. Check the logs for errors

### Issue: "Invalid API key"
**Make sure:**
- You're sending the `X-Api-Key` header with requests
- The key matches what's in the environment: `dev-test-key`

## File Structure

After testing, your mamlarr directory will look like:

```
mamlarr/
├── pyproject.toml              # Package definition
├── uv.lock                     # Locked dependencies
├── .venv/                      # Virtual environment (created by uv)
├── mamlarr_service/            # Main service code
│   ├── __init__.py
│   ├── api.py                  # FastAPI routes
│   ├── settings.py             # Configuration
│   ├── models.py               # Data models
│   ├── mam_client.py           # MyAnonymouse client
│   ├── transmission.py         # Transmission RPC client
│   ├── manager.py              # Download manager
│   ├── postprocess.py          # Audio file processing
│   ├── store.py                # Job storage
│   └── log.py                  # Logging
├── dev/
│   ├── __init__.py
│   └── mock_tracker.py         # Mock MAM + Transmission server
├── output/                     # Test output files
│   ├── mock_book_1/           # Processed audiobook
│   └── tmp/                   # Temp files
├── run_dev_server.sh          # Start in mock mode
├── test_with_mock_tracker.sh  # Start with mock HTTP server
├── test_api.sh                # Manual API tests
├── quick_test.py              # Python validation
├── TESTING.md                 # Testing guide
├── OFFLINE_TESTING_SETUP.md   # This file
├── README.md                  # Original readme
└── ROADMAP.md                 # Development roadmap
```

## Next Steps

### For Offline Testing
1. Run through the testing checklist above
2. Test integration with AudioBookRequest
3. Verify all API endpoints work as expected

### Moving to Production
When ready to test with real MyAnonymouse and Transmission:

1. Get your MyAnonymouse session cookie:
   - Log into MyAnonymouse
   - Open browser dev tools → Application → Cookies
   - Copy the `mam_id` cookie value

2. Set up environment variables:
   ```bash
   export MAM_SERVICE_USE_MOCK_DATA="false"
   export MAM_SERVICE_MAM_SESSION_ID="your_real_mam_cookie"
   export MAM_SERVICE_TRANSMISSION_URL="http://your-seedbox:9091/transmission/rpc"
   export MAM_SERVICE_TRANSMISSION_USERNAME="your_username"
   export MAM_SERVICE_TRANSMISSION_PASSWORD="your_password"
   export MAM_SERVICE_DOWNLOAD_DIRECTORY="/mnt/storage/audiobooks"
   export MAM_SERVICE_SEED_TARGET_HOURS="72"  # MyAnonymouse requirement
   export MAM_SERVICE_ENABLE_AUDIO_MERGE="true"  # Enable ffmpeg merging
   ```

3. Start the service:
   ```bash
   uvicorn mamlarr_service.api:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

All endpoints require `X-Api-Key` header (except `/health`).

### GET `/health`
Health check endpoint.
```bash
curl http://localhost:8000/health
```

### GET `/api/v1/indexer`
Returns list of indexers (Prowlarr-compatible).
```bash
curl -H "X-Api-Key: dev-test-key" http://localhost:8000/api/v1/indexer
```

### GET `/api/v1/search`
Search for audiobooks (Prowlarr-compatible).
```bash
curl -H "X-Api-Key: dev-test-key" \
  "http://localhost:8000/api/v1/search?query=Foundation&limit=10&offset=0"
```

### POST `/api/v1/search`
Download a release (Prowlarr-compatible).
```bash
curl -X POST \
  -H "X-Api-Key: dev-test-key" \
  -H "Content-Type: application/json" \
  -d '{"guid":"mam-1001","indexerId":801001}' \
  http://localhost:8000/api/v1/search
```

### GET `/api/v1/jobs/{jobId}`
Check job status.
```bash
curl -H "X-Api-Key: dev-test-key" \
  http://localhost:8000/api/v1/jobs/JOB_ID_HERE
```

## Troubleshooting Commands

```bash
# Check if mamlarr is running
lsof -i :8000

# Check logs (if running in background)
tail -f /tmp/mamlarr.log

# Test Python imports
python -c "from mamlarr_service.api import app; print('OK')"

# Check output directory
ls -lah output/

# Kill all uvicorn processes
pkill uvicorn
```

## Need Help?

If you're still having issues:

1. **Check the service logs** - Look for error messages when starting
2. **Verify dependencies** - Run `uv sync` again
3. **Test step-by-step** - Run `quick_test.py` first, then try the server
4. **Check ports** - Make sure ports 8000 and 8001 are available

The service is designed to work offline with mock data, so if you're having connection issues, make sure `MAM_SERVICE_USE_MOCK_DATA="true"` is set.
