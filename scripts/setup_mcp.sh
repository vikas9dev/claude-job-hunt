#!/usr/bin/env bash
# ============================================================================
# setup_mcp.sh — install the JobSpy MCP server used by /job-feed.
#
#   bash scripts/setup_mcp.sh
#
# What it does:
#   1. Clones borgius/jobspy-mcp-server into ./mcp_servers/ (gitignored)
#   2. Installs its npm deps with the version pins it needs
#   3. Builds the `jobspy` Docker image the server shells out to
#   4. Writes ./.mcp.json (gitignored — it holds absolute paths)
#
# Needs: git, Node.js 18+, npm, Docker (running). No API key.
# Safe to re-run: it pulls the latest and rewrites .mcp.json.
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MCP_DIR="$REPO_DIR/mcp_servers"
JOBSPY_DIR="$MCP_DIR/jobspy-mcp-server"
JOBSPY_REPO="https://github.com/borgius/jobspy-mcp-server.git"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
step()  { echo -e "\n${GREEN}==>${NC} $1"; }

step "Checking prerequisites..."
command -v git  >/dev/null 2>&1 || { error "git not found"; exit 1; }
command -v node >/dev/null 2>&1 || { error "Node.js not found — install 18+ from https://nodejs.org/"; exit 1; }
command -v npm  >/dev/null 2>&1 || { error "npm not found (comes with Node.js)"; exit 1; }
log "Node.js $(node -v), npm $(npm -v)"

mkdir -p "$MCP_DIR"

step "Fetching JobSpy MCP server..."
if [ -d "$JOBSPY_DIR/.git" ]; then
    (cd "$JOBSPY_DIR" && git pull --ff-only >/dev/null 2>&1) && log "Pulled latest" || warn "git pull failed — using the existing copy"
else
    git clone --depth 1 "$JOBSPY_REPO" "$JOBSPY_DIR"
fi

step "Installing npm dependencies..."
cd "$JOBSPY_DIR"
# jobspy's schemas are written for zod v3. Newer MCP SDKs pull zod v4, which
# can't serialize v3 schemas → search_jobs registers with an empty input schema
# and the client drops the tool. Force one zod v3 across the tree.
npm pkg set 'overrides.zod=3.25.76'
npm install --silent
# jobspy targets the old prompt()/tool() API. SDK >= 1.17 crashes at start-up
# ("Cannot read properties of null (reading '_zod')"). 1.12.3 works.
npm install @modelcontextprotocol/sdk@1.12.3 --silent
log "npm deps installed (MCP SDK 1.12.3, zod v3)"

# Clear error when Docker is down, instead of an opaque MCP failure.
PATCH="$REPO_DIR/scripts/patches/jobspy-docker-preflight.patch"
if grep -q "JobSpy requires Docker" "$JOBSPY_DIR/src/tools/search-jobs.js" 2>/dev/null; then
    log "Docker pre-flight patch already applied"
elif [ -f "$PATCH" ] && patch -p1 --dry-run < "$PATCH" >/dev/null 2>&1; then
    patch -p1 < "$PATCH" >/dev/null 2>&1 && log "Docker pre-flight patch applied" || warn "Patch failed — JobSpy still works"
else
    warn "Docker pre-flight patch skipped (upstream file changed) — JobSpy still works"
fi

step "Building the jobspy Docker image..."
# The server runs `docker run --rm jobspy …`, so the image MUST exist.
if command -v docker >/dev/null 2>&1 && docker version >/dev/null 2>&1; then
    if docker build -t jobspy "$JOBSPY_DIR/jobspy" >/dev/null; then
        log "Docker image 'jobspy' built"
    else
        warn "Image build failed — retry: docker build -t jobspy \"$JOBSPY_DIR/jobspy\""
    fi
else
    warn "Docker is not running. Start it (WSL: Docker Desktop → Settings → Resources → WSL Integration), then:"
    warn "  docker build -t jobspy \"$JOBSPY_DIR/jobspy\""
fi

step "Writing .mcp.json..."
MCP_JSON="$REPO_DIR/.mcp.json"
if [ -f "$MCP_JSON" ] && ! grep -q '"jobspy"' "$MCP_JSON"; then
    cp "$MCP_JSON" "$MCP_JSON.bak"
    warn "Existing .mcp.json had other servers — saved a copy as .mcp.json.bak; merge them back by hand"
fi
cat > "$MCP_JSON" << EOF
{
  "mcpServers": {
    "jobspy": {
      "type": "stdio",
      "command": "node",
      "args": ["$JOBSPY_DIR/src/index.js"],
      "env": {}
    }
  }
}
EOF
log "Wrote $MCP_JSON"

echo ""
echo "Done. Restart Claude Code in this folder and approve the 'jobspy' MCP server."
echo "Test it with:  /job-feed dry-run"
