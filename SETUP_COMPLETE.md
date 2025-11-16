# ✅ Mamlarr Offline Testing Setup - COMPLETE

## What Was Done

I've set up a complete offline testing environment for your mamlarr service so you can test it without needing real MyAnonymouse credentials or a Transmission server.

## Files Created

### Configuration
- ✅ **`pyproject.toml`** - Package definition with all dependencies
- ✅ Dependencies installed via `uv sync`

### Testing Scripts (All Executable)
- ✅ **`run_dev_server.sh`** - Start mamlarr in pure mock mode (recommended)
- ✅ **`test_with_mock_tracker.sh`** - Start with mock MAM + Transmission HTTP server
- ✅ **`test_api.sh`** - Quick curl-based API endpoint tests
- ✅ **`quick_test.py`** - Python validation script
- ✅ **`test_offline.py`** - Comprehensive offline test suite

### Documentation
- ✅ **`TESTING.md`** - Comprehensive testing guide with examples
- ✅ **`OFFLINE_TESTING_SETUP.md`** - Complete setup guide with troubleshooting
- ✅ **`README.md`** - Updated with offline testing instructions

## How to Test (3 Simple Steps)

### Step 1: Start the Service
```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
./run_dev_server.sh
```

You should see:
```
Starting mamlarr in OFFLINE/MOCK mode...
Mamlarr will be available at: http://localhost:8000
Configure AudioBookRequest Prowlarr settings:
  - URL: http://localhost:8000
  - API Key: dev-test-key
```

### Step 2: Test the API
Open a new terminal and run:
```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
./test_api.sh
```

Or visit http://localhost:8000/docs in your browser to see the interactive API documentation.

### Step 3: Test with AudioBookRequest
1. Keep mamlarr running from Step 1
2. Open AudioBookRequest
3. Configure Prowlarr settings:
   - **Base URL**: `http://localhost:8000`
   - **API Key**: `dev-test-key`
4. Test the connection - you should see "MyAnonamouse" indexer
5. Try searching for audiobooks - searches will go through mamlarr's mock backend

## What the Mock Mode Does

When running in mock mode (`MAM_SERVICE_USE_MOCK_DATA=true`):

✅ **Search Endpoint** - Returns 1 fake audiobook result
✅ **Download Endpoint** - Creates a mock download job
✅ **Transmission Client** - Uses in-memory mock (no real Transmission needed)
✅ **File Processing** - Creates a fake audiobook file in `./output/`
✅ **Job Tracking** - Tracks job status from queued → downloading → seeding → completed
✅ **Seeding** - Skips seeding delay (set to 0 hours for testing)
✅ **Post-processing** - Simulates file copying without requiring ffmpeg

## Available Test Commands

```bash
# Quick validation (no server needed)
python quick_test.py

# Start development server (mock mode)
./run_dev_server.sh

# Test all API endpoints (requires server running)
./test_api.sh

# Start with mock HTTP tracker (more realistic)
./test_with_mock_tracker.sh

# View API documentation
# Open browser: http://localhost:8000/docs
```

## API Endpoints

All endpoints are Prowlarr-compatible:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (no auth required) |
| `/api/v1/indexer` | GET | List indexers (returns MyAnonymouse) |
| `/api/v1/search` | GET | Search for audiobooks |
| `/api/v1/search` | POST | Download a release |
| `/api/v1/jobs/{jobId}` | GET | Get job status |

All endpoints except `/health` require the `X-Api-Key` header.

## Example API Flow

```bash
# 1. Search
curl -H "X-Api-Key: dev-test-key" \
  "http://localhost:8000/api/v1/search?query=Foundation&limit=10"

# Response includes guid and indexerId, use them for download:

# 2. Download
curl -X POST \
  -H "X-Api-Key: dev-test-key" \
  -H "Content-Type: application/json" \
  -d '{"guid":"mam-1001","indexerId":801001}' \
  http://localhost:8000/api/v1/search

# Response includes jobId, use it to check status:

# 3. Check status
curl -H "X-Api-Key: dev-test-key" \
  "http://localhost:8000/api/v1/jobs/YOUR_JOB_ID"
```

## What Gets Created

After running a test download, you'll find:

```
mamlarr/
├── output/
│   ├── mock_book_1/          # Processed audiobook
│   │   └── track1.mp3       # Mock audio file
│   └── tmp/
│       └── mock_transmission/ # Temp download location
└── .venv/                    # Python virtual environment
```

## Common Issues You Were Likely Facing

### Issue #1: Missing Dependencies
**Before:** No pyproject.toml, dependencies not defined
**Fixed:** Created pyproject.toml with all required packages

### Issue #2: No Easy Way to Test Offline
**Before:** Required real MAM session cookie and Transmission server
**Fixed:** Added `use_mock_data` mode with in-memory mocks

### Issue #3: Complex Setup Process
**Before:** Manual environment variable configuration
**Fixed:** Created `run_dev_server.sh` with sensible defaults

### Issue #4: No Testing Documentation
**Before:** Unclear how to validate the service works
**Fixed:** Created comprehensive testing guides and scripts

## Troubleshooting

### "Module not found" error
```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
uv sync
```

### "Port 8000 already in use"
```bash
# Kill existing process
lsof -ti:8000 | xargs kill

# Or change port in run_dev_server.sh
```

### "Permission denied" on scripts
```bash
chmod +x *.sh *.py
```

### Downloads not completing
Make sure you're in mock mode:
```bash
export MAM_SERVICE_USE_MOCK_DATA="true"
export MAM_SERVICE_SEED_TARGET_HOURS="0"
```

## Next Steps

### For Testing
1. ✅ Run `./run_dev_server.sh`
2. ✅ Run `./test_api.sh` to verify all endpoints
3. ✅ Connect AudioBookRequest to test integration
4. ✅ Try searching and downloading through AudioBookRequest

### For Production
When ready to use real services:

1. Get your MyAnonymouse session cookie (`mam_id`)
2. Configure Transmission server details
3. Update environment variables in a `.env` file:
   ```bash
   MAM_SERVICE_USE_MOCK_DATA=false
   MAM_SERVICE_MAM_SESSION_ID=your_real_cookie
   MAM_SERVICE_TRANSMISSION_URL=http://your-seedbox:9091/transmission/rpc
   MAM_SERVICE_TRANSMISSION_USERNAME=username
   MAM_SERVICE_TRANSMISSION_PASSWORD=password
   MAM_SERVICE_DOWNLOAD_DIRECTORY=/mnt/storage/audiobooks
   MAM_SERVICE_SEED_TARGET_HOURS=72
   MAM_SERVICE_ENABLE_AUDIO_MERGE=true
   ```
4. Start: `uvicorn mamlarr_service.api:app --host 0.0.0.0 --port 8000`

## Testing Checklist

Use this checklist to verify everything works:

- [ ] Dependencies installed (`uv sync` completed)
- [ ] Service starts without errors (`./run_dev_server.sh`)
- [ ] Health endpoint responds (`curl http://localhost:8000/health`)
- [ ] Indexer endpoint returns MyAnonymouse
- [ ] Search endpoint returns mock results
- [ ] Download endpoint creates job
- [ ] Job status endpoint returns job info
- [ ] AudioBookRequest can connect to mamlarr as Prowlarr
- [ ] Searches from AudioBookRequest work
- [ ] Files appear in `./output/` directory

## Documentation

- **Quick Start**: See [README.md](README.md)
- **Testing Guide**: See [TESTING.md](TESTING.md)
- **Complete Setup**: See [OFFLINE_TESTING_SETUP.md](OFFLINE_TESTING_SETUP.md)
- **Development Roadmap**: See [ROADMAP.md](ROADMAP.md)

## Summary

Your mamlarr service is now fully set up for offline testing! You can:

✅ Test without MyAnonymouse credentials
✅ Test without Transmission server
✅ Test the full workflow from search → download → process
✅ Integrate with AudioBookRequest immediately
✅ Validate all API endpoints work correctly

Run `./run_dev_server.sh` and start testing!
