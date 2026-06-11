#!/usr/bin/env bash
# 本机 node 过旧时，用 conda 环境里的 Node 20 启动开发服务器（约几秒起服务）
set -euo pipefail
cd "$(dirname "$0")"
exec conda run -n paper2ppt-fe --no-capture-output npm run dev -- --host 0.0.0.0 --port 5173
