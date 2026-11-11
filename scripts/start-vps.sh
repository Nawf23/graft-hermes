#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../deploy"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Stop here and tell your Graft helper; do not change your bot setup."
  exit 1
fi
if docker container inspect graft-demo-kanboard >/dev/null 2>&1; then
  echo "The Graft demo container already exists. Its state is:"
  docker container inspect --format '{{.State.Status}}' graft-demo-kanboard
  echo "No container was changed. Ask your helper before making changes."
  exit 0
fi
if command -v ss >/dev/null 2>&1 && ss -lntH | awk '{print $4}' | grep -qE ':8460$'; then
  echo "Port 8460 is already in use. Stop here; we will select a different port."
  exit 1
fi
docker run -d --name graft-demo-kanboard --restart unless-stopped \
  --memory 256m --cpus 0.50 --log-opt max-size=5m --log-opt max-file=2 \
  -p 127.0.0.1:8460:80 -v graft-demo-data:/var/www/app/data \
  kanboard/kanboard:v1.2.57@sha256:637989624e5362af2b97bfb4be1936fb6b111ea7cbdffea0ae8bd3068dc84125
echo "Graft's Kanboard demo is running on server-local port 8460. Your existing bots were not restarted."
echo "Open it from your Mac through the SSH tunnel described in START-HERE.md."
