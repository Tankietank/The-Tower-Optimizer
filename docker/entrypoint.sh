#!/bin/sh
set -eu

DATA_ROOT="${TOWER_OPTIMIZER_DATA_DIR:-/app/data}"
mkdir -p \
    "${DATA_ROOT}/profiles" \
    "${DATA_ROOT}/custom_icons" \
    "${DATA_ROOT}/game_updates" \
    "${DATA_ROOT}/backups" \
    "${DATA_ROOT}/imports"

exec python -m streamlit run app.py \
    --server.address="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}" \
    --server.port="${STREAMLIT_SERVER_PORT:-8501}" \
    --server.headless=true \
    --browser.gatherUsageStats=false
