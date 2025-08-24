#!/usr/bin/env bash
set -euo pipefail

API_BASE="${1:-http://127.0.0.1:8000}"

cd "$(dirname "$0")/../frontend/dashboard"
export VITE_API_BASE="$API_BASE"
npm run dev


