#!/usr/bin/env bash

set -Eeuo pipefail

MODE="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

case "${MODE}" in
  local)
    DEFAULT_WEB_PORT=3000
    ACCESS_HOST=localhost
    ;;
  server)
    DEFAULT_WEB_PORT=80
    ACCESS_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
    ACCESS_HOST="${ACCESS_HOST:-localhost}"
    ;;
  *)
    echo "Usage: $0 [local|server]" >&2
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is unavailable. Install the Docker Compose plugin first." >&2
  exit 1
fi

export SHRIMP_WEB_PORT="${SHRIMP_WEB_PORT:-${DEFAULT_WEB_PORT}}"

cd "${PROJECT_ROOT}"

echo "Starting shrimp-analysis in ${MODE} mode..."
echo "Web port: ${SHRIMP_WEB_PORT}"
docker compose up --build -d

HEALTH_URL="http://127.0.0.1:${SHRIMP_WEB_PORT}/api/health"
if command -v curl >/dev/null 2>&1; then
  for _ in {1..60}; do
    if curl --fail --silent --show-error "${HEALTH_URL}" >/dev/null 2>&1; then
      echo "Health check passed: ${HEALTH_URL}"
      break
    fi
    sleep 1
  done

  if ! curl --fail --silent --show-error "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "Services started, but the health check did not pass within 60 seconds." >&2
    echo "Inspect logs with: docker compose logs --tail=200" >&2
    docker compose ps
    exit 1
  fi
fi

docker compose ps
echo "Web: http://${ACCESS_HOST}:${SHRIMP_WEB_PORT}/"

