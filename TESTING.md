# Mamlarr Offline Testing Guide

This guide explains how to test mamlarr offline without needing real MyAnonymouse credentials or a Transmission server.

## Quick Start

### Option 1: Pure Mock Mode (Fastest)

This uses in-memory mocks for everything - no external services needed.

```bash
# Install dependencies
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
uv sync

# Run the dev server
./run_dev_server.sh
```

The service will be available at `http://localhost:8000` with API key `dev-test-key`.

### Option 2: Mock Tracker Mode (More Realistic)

This runs a fake MyAnonymouse and Transmission server locally.

```bash
# Start both services
./test_with_mock_tracker.sh
```

This starts:
- Mock tracker at `http://localhost:8001` (simulates MAM + Transmission)
- Mamlarr API at `http://localhost:8000`

## Manual Testing with curl

Once the service is running, you can test it manually:

```bash
# Set API key
API_KEY="dev-test-key"
BASE_URL="http://localhost:8000"

# 1. Health check
curl "$BASE_URL/health"

# 2. Get indexers
curl -H "X-Api-Key: $API_KEY" "$BASE_URL/api/v1/indexer"

# 3. Search for audiobooks
curl -H "X-Api-Key: $API_KEY" "$BASE_URL/api/v1/search?query=test&limit=10&offset=0"

# 4. Download (use GUID from search results)
curl -X POST \
  -H "X-Api-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"guid":"mam-1001","indexerId":801001}' \
  "$BASE_URL/api/v1/search"

# 5. Check job status (use jobId from download response)
curl -H "X-Api-Key: $API_KEY" "$BASE_URL/api/v1/jobs/JOB_ID_HERE"
```

## Automated Testing

Run the comprehensive test suite:

```bash
# Install test dependencies
uv sync --dev

# Run the test
python test_offline.py
```

## Integration with AudioBookRequest

To test mamlarr with AudioBookRequest:

1. Start mamlarr in mock mode:
   ```bash
   ./run_dev_server.sh
   ```

2. Configure AudioBookRequest's Prowlarr settings:
   - URL: `http://localhost:8000`
   - API Key: `dev-test-key`

3. In AudioBookRequest, try searching for audiobooks. The search will go through mamlarr's mock backend.

## Configuration Options

You can customize the mock mode by setting environment variables:

```bash
# API configuration
export MAM_SERVICE_API_KEY="your-api-key"
export MAM_SERVICE_INDEXER_ID="801001"
export MAM_SERVICE_INDEXER_NAME="MyAnonamouse"

# Mock mode settings
export MAM_SERVICE_USE_MOCK_DATA="true"
export MAM_SERVICE_DOWNLOAD_DIRECTORY="./output"
export MAM_SERVICE_POSTPROCESS_TMP_DIR="./output/tmp"
export MAM_SERVICE_SEED_TARGET_HOURS="0"
export MAM_SERVICE_ENABLE_AUDIO_MERGE="false"

# For mock tracker mode (Option 2)
export MAM_SERVICE_MAM_BASE_URL="http://localhost:8001"
export MAM_SERVICE_TRANSMISSION_URL="http://localhost:8001/transmission/rpc"
```

## Troubleshooting

### "Module not found" errors
```bash
cd /home/marc/Documents/github/AudioBookRequest/mamlarr
uv sync
```

### Port already in use
Change the port in the run scripts:
```bash
# In run_dev_server.sh, change:
uvicorn mamlarr_service.api:app --reload --port 8002
```

### Mock downloads not completing
Check that:
- `MAM_SERVICE_SEED_TARGET_HOURS` is set to `0` for testing
- Output directory exists and is writable: `mkdir -p output/tmp`

### API key errors
Ensure you're sending the `X-Api-Key` header with every request:
```bash
curl -H "X-Api-Key: dev-test-key" http://localhost:8000/api/v1/indexer
```

## What Gets Tested

### Pure Mock Mode
- ✓ Search endpoint returns mock results
- ✓ Download creates mock torrent job
- ✓ Post-processing creates mock audiobook file
- ✓ Job status tracking works

### Mock Tracker Mode
- ✓ Full HTTP round-trip to mock MAM API
- ✓ Torrent file download simulation
- ✓ Transmission RPC communication
- ✓ Complete download → seed → process workflow

## Output Structure

When testing, files are created in:
```
mamlarr/
├── output/
│   ├── mock_book_1/          # Processed audiobook
│   └── tmp/
│       └── mock_transmission/ # Temp download location
```

## Next Steps

Once offline testing works, you can move to testing with real services:

1. Get a MyAnonymouse session cookie
2. Set up Transmission on your seedbox
3. Update environment variables with real credentials
4. Set `MAM_SERVICE_USE_MOCK_DATA="false"`
