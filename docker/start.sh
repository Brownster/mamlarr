#!/usr/bin/env bash
set -euo pipefail

cd /srv/audiobookrequest
uvicorn app.main:app --host 0.0.0.0 --port "${AUDIOBOOKREQUEST_PORT:-8000}" &
ABR_PID=$!

cd /srv/mamlarr
uvicorn mamlarr_service.api:app --host 0.0.0.0 --port "${MAMLARR_PORT:-8800}" &
MAMLARR_PID=$!

wait $ABR_PID $MAMLARR_PID
