#!/bin/bash
# Test mamlarr with the mock MAM/Transmission server
# This script starts both the mock tracker and mamlarr service

set -e

echo "Starting Mock Tracker + Mamlarr Integration Test"
echo "================================================="

# Start mock tracker in background
echo "Starting mock tracker on port 8001..."
uvicorn dev.mock_tracker:app --port 8001 &
MOCK_PID=$!
echo "Mock tracker PID: $MOCK_PID"

# Give it time to start
sleep 2

# Configure mamlarr to use mock tracker
export MAM_SERVICE_API_KEY="dev-test-key"
export MAM_SERVICE_MAM_SESSION_ID="mock-session"
export MAM_SERVICE_MAM_BASE_URL="http://localhost:8001"
export MAM_SERVICE_TRANSMISSION_URL="http://localhost:8001/transmission/rpc"
export MAM_SERVICE_DOWNLOAD_DIRECTORY="./output"
export MAM_SERVICE_POSTPROCESS_TMP_DIR="./output/tmp"
export MAM_SERVICE_SEED_TARGET_HOURS="0"
export MAM_SERVICE_ENABLE_AUDIO_MERGE="false"
export MAM_SERVICE_USE_MOCK_DATA="false"  # Use real endpoints pointing to mock server

echo ""
echo "Starting mamlarr on port 8000..."
uvicorn mamlarr_service.api:app --port 8000 &
MAMLARR_PID=$!
echo "Mamlarr PID: $MAMLARR_PID"

echo ""
echo "================================================="
echo "Services are running:"
echo "  - Mock Tracker: http://localhost:8001"
echo "  - Mamlarr API: http://localhost:8000"
echo ""
echo "Configure AudioBookRequest Prowlarr settings:"
echo "  - URL: http://localhost:8000"
echo "  - API Key: dev-test-key"
echo ""
echo "Press Ctrl+C to stop all services"
echo "================================================="

# Cleanup function
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $MAMLARR_PID 2>/dev/null || true
    kill $MOCK_PID 2>/dev/null || true
    echo "Services stopped."
    exit 0
}

trap cleanup EXIT INT TERM

# Wait for interrupt
wait
