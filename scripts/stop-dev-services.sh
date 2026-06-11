#!/usr/bin/env bash
set -euo pipefail

systemctl --user stop paper2ppt-frontend.service paper2ppt-api.service 2>/dev/null || true
echo "Paper2PPT dev services stopped."
