#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NHAI Tender Intelligence — Server Startup Script
# Usage: bash run_servers.sh [port]
# Default port: 8000
# Example: bash run_servers.sh 8001
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8000}"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  NHAI Tender Intelligence — Starting Services"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. Kill any existing processes on our port ────────────────────────────────
echo "► Stopping any running services on port $PORT..."
lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null && echo "  Killed existing process on :$PORT" || echo "  Port $PORT is free"
echo ""

# ── 2. Check Python environment ───────────────────────────────────────────────
echo "► Checking Python environment..."
if ! python3 -c "import fastapi, uvicorn, supabase, httpx, pdfplumber" 2>/dev/null; then
    echo "  Installing dependencies..."
    pip3 install -r requirements.txt -q
fi
echo "  ✓ Python dependencies OK"
echo ""

# ── 3. Validate .env ──────────────────────────────────────────────────────────
echo "► Validating configuration..."
if [ ! -f ".env" ]; then
    echo "  ✗ ERROR: .env file not found!"
    exit 1
fi
source_url=$(grep 'SUPABASE_URL' .env | cut -d= -f2-)
eyq_key=$(grep 'EYQ_INCUBATOR_KEY' .env | cut -d= -f2-)
echo "  Supabase URL: ${source_url:0:40}..."
echo "  EYQ API Key : ${eyq_key:0:8}..."
echo ""

# ── 4. Start the FastAPI backend ──────────────────────────────────────────────
echo "► Starting FastAPI backend on http://localhost:$PORT"
echo "  • Dashboard:  http://localhost:$PORT"
echo "  • API docs:   http://localhost:$PORT/docs"
echo "  • Tenders:    http://localhost:$PORT/api/tenders"
echo ""
echo "  Press Ctrl+C to stop."
echo ""
echo "═══════════════════════════════════════════════════════"
echo ""

python3 -m uvicorn server:app \
    --host 127.0.0.1 \
    --port $PORT \
    --reload \
    --log-level info \
    --access-log

