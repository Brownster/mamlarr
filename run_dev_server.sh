#!/bin/bash
# Development server script for mamlarr - runs in mock mode for offline testing

set -e

echo "Starting mamlarr in OFFLINE/MOCK mode..."
echo "============================================"

export MAM_SERVICE_API_KEY="dev-test-key"
export MAM_SERVICE_MAM_SESSION_ID="not-needed"
export MAM_SERVICE_USE_MOCK_DATA="true"
export MAM_SERVICE_DOWNLOAD_DIRECTORY="./output"
export MAM_SERVICE_POSTPROCESS_TMP_DIR="./output/tmp"
export MAM_SERVICE_SEED_TARGET_HOURS="0"
export MAM_SERVICE_ENABLE_AUDIO_MERGE="false"

echo ""
echo "Configuration:"
echo "  API Key: $MAM_SERVICE_API_KEY"
echo "  Mock Mode: $MAM_SERVICE_USE_MOCK_DATA"
echo "  Output Directory: $MAM_SERVICE_DOWNLOAD_DIRECTORY"
echo ""
echo "Mamlarr will be available at: http://localhost:8000"
echo "Configure AudioBookRequest Prowlarr settings:"
echo "  - URL: http://localhost:8000"
echo "  - API Key: dev-test-key"
echo ""
echo "============================================"

# Run with uvicorn
uvicorn mamlarr_service.api:app --reload --port 8000
