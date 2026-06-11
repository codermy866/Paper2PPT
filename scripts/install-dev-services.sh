#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
LOG_DIR="$ROOT/agent/runtime/logs"

mkdir -p "$LOG_DIR" "$UNIT_DIR"

NODE_BIN="$(command -v node)"
if [[ -z "$NODE_BIN" ]]; then
  echo "error: node not found in PATH" >&2
  exit 1
fi

cp "$ROOT/scripts/paper2ppt-api.service" "$UNIT_DIR/paper2ppt-api.service"
sed "s|@NODE@|$NODE_BIN|g" "$ROOT/scripts/paper2ppt-frontend.service" > "$UNIT_DIR/paper2ppt-frontend.service"

systemctl --user daemon-reload
systemctl --user enable paper2ppt-api.service paper2ppt-frontend.service
systemctl --user restart paper2ppt-api.service paper2ppt-frontend.service

echo ""
echo "Paper2PPT dev services are running (auto-restart on crash)."
echo "  Workspace: http://127.0.0.1:5173/workspace"
echo "  LAN:       http://$(hostname -I 2>/dev/null | awk '{print $1}'):5173/workspace"
echo "  API:       http://127.0.0.1:8001/api/health"
echo ""
systemctl --user --no-pager status paper2ppt-api.service paper2ppt-frontend.service || true
