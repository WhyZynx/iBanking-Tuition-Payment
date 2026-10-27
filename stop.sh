#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
command -v docker >/dev/null 2>&1 || { printf 'Docker CLI was not found.\n' >&2; exit 1; }
[[ -f .env.docker ]] || { printf '.env.docker is missing; nothing was stopped.\n' >&2; exit 1; }
docker compose --env-file .env.docker -p ibanking-demo stop
printf 'iBanking services stopped. Database volume and .env.docker were preserved.\n'
