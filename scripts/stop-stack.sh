#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is unavailable. Install the Docker Compose plugin first." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

echo "Stopping shrimp-analysis services..."
docker compose down --remove-orphans
echo "Services stopped. PostgreSQL, Redis, uploads, and job data volumes were preserved."

