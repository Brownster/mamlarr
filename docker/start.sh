#!/usr/bin/env bash
set -euo pipefail

# Start AudioBookRequest on port 8000
echo "Starting AudioBookRequest on port ${AUDIOBOOKREQUEST_PORT:-8000}"
uvicorn app.main:app --host 0.0.0.0 --port "${AUDIOBOOKREQUEST_PORT:-8000}" &
ABR_PID=$!

# Start Mamlarr on port 8800
echo "Starting Mamlarr on port ${MAMLARR_PORT:-8800}"
uvicorn mamlarr_service.api:app --host 0.0.0.0 --port "${MAMLARR_PORT:-8800}" &
MAMLARR_PID=$!

wait $ABR_PID $MAMLARR_PID
