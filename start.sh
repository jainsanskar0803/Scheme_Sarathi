#!/bin/bash
# Scheme Sarathi — one-click start script
# Starts both the backend (FastAPI) and frontend (Next.js) in one terminal.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_LOG="$ROOT/.backend.log"
FRONTEND_LOG="$ROOT/.frontend.log"
BACKEND_PID_FILE="$ROOT/.backend.pid"
FRONTEND_PID_FILE="$ROOT/.frontend.pid"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▶  $*${RESET}"; }
success() { echo -e "${GREEN}✓  $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠  $*${RESET}"; }
error()   { echo -e "${RED}✗  $*${RESET}"; exit 1; }

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  echo ""
  info "Shutting down…"
  [ -f "$BACKEND_PID_FILE" ]  && kill "$(cat "$BACKEND_PID_FILE")"  2>/dev/null; rm -f "$BACKEND_PID_FILE"
  [ -f "$FRONTEND_PID_FILE" ] && kill "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; rm -f "$FRONTEND_PID_FILE"
  success "Stopped. Goodbye."
}
trap cleanup EXIT INT TERM

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Scheme Sarathi — Starting Up       ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  error ".env file not found at $ROOT/.env\n   Copy .env.example and fill in your keys."
fi
source "$ROOT/.env"

[ -z "$SARVAM_API_KEY" ]     && warn "SARVAM_API_KEY is not set in .env"
[ -z "$SUPABASE_URL" ]       && warn "SUPABASE_URL is not set in .env"
[ -z "$SUPABASE_SERVICE_KEY" ] && warn "SUPABASE_SERVICE_KEY is not set in .env"

# ── Check Python ──────────────────────────────────────────────────────────────
info "Checking Python environment…"
if ! command -v python3 &>/dev/null; then
  error "python3 not found. Install Python 3.10+."
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PYTHON_VERSION found"

if ! python3 -c "import fastapi, uvicorn, supabase, httpx, pydantic" 2>/dev/null; then
  info "Installing Python dependencies…"
  pip3 install -r "$ROOT/requirements.txt" --quiet
fi
success "Python dependencies OK"

# ── Check Node ────────────────────────────────────────────────────────────────
info "Checking Node environment…"
if ! command -v node &>/dev/null; then
  error "node not found. Install Node.js 18+."
fi
NODE_VERSION=$(node -e "console.log(process.versions.node)")
info "Node $NODE_VERSION found"

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  info "Installing frontend dependencies…"
  cd "$ROOT/frontend" && npm install --silent
  cd "$ROOT"
fi
success "Node dependencies OK"

# ── Start Backend ─────────────────────────────────────────────────────────────
info "Starting FastAPI backend on http://localhost:8000 …"
cd "$ROOT"
SARVAM_API_KEY="$SARVAM_API_KEY" \
SUPABASE_URL="$SUPABASE_URL" \
SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" \
USE_SUPABASE="${USE_SUPABASE:-true}" \
python3 -m uvicorn backend.main:app --port 8000 --log-level warning > "$BACKEND_LOG" 2>&1 &
echo $! > "$BACKEND_PID_FILE"

# Wait for backend to be ready
for i in {1..15}; do
  sleep 1
  if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    success "Backend is ready"
    break
  fi
  if [ $i -eq 15 ]; then
    error "Backend failed to start. Check $BACKEND_LOG for details."
  fi
done

# ── Start Frontend ────────────────────────────────────────────────────────────
info "Starting Next.js frontend on http://localhost:3000 …"
cd "$ROOT/frontend"
npm run dev > "$FRONTEND_LOG" 2>&1 &
echo $! > "$FRONTEND_PID_FILE"
cd "$ROOT"

# Wait for frontend to be ready
for i in {1..30}; do
  sleep 1
  if curl -s http://localhost:3000 > /dev/null 2>&1; then
    success "Frontend is ready"
    break
  fi
  if [ $i -eq 30 ]; then
    error "Frontend failed to start. Check $FRONTEND_LOG for details."
  fi
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Scheme Sarathi is running!               ${RESET}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════${RESET}"
echo ""
echo -e "  🌐  App:      ${BOLD}http://localhost:3000${RESET}"
echo -e "  🔧  API docs: ${BOLD}http://localhost:8000/docs${RESET}"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop both servers."
echo ""

# ── Keep alive ────────────────────────────────────────────────────────────────
wait
