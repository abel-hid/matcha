#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if (( $# != 0 )); then
  echo "Usage: ./start.sh" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is required." >&2
  exit 1
fi

if [[ ! -f backend/.env ]]; then
  echo "backend/.env is missing." >&2
  echo "Create it with: cp backend/.env.example backend/.env" >&2
  exit 1
fi

mkdir -p backend/uploads

COMPOSE=(docker compose --env-file backend/.env -f docker-compose.yml)

# Remove the legacy database-only container from the previous runtime while
# preserving its named PostgreSQL volume.
if docker ps -a --format '{{.Names}}' | grep -qx 'matcha_db'; then
  docker rm -f matcha_db >/dev/null
fi

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build backend frontend schema seed
"${COMPOSE[@]}" up -d db

for attempt in $(seq 1 40); do
  if "${COMPOSE[@]}" exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    break
  fi

  if (( attempt == 40 )); then
    echo "PostgreSQL did not become ready." >&2
    "${COMPOSE[@]}" logs --tail=100 db >&2
    exit 1
  fi

  sleep 1
done

"${COMPOSE[@]}" run --rm schema
"${COMPOSE[@]}" run --rm seed
"${COMPOSE[@]}" up -d backend frontend

for service in backend frontend; do
  container_id="$("${COMPOSE[@]}" ps -q "$service")"

  if [[ -z "$container_id" ]]; then
    echo "The $service container was not created." >&2
    exit 1
  fi

  for attempt in $(seq 1 60); do
    health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"

    if [[ "$health_status" == "healthy" ]]; then
      break
    fi

    if [[ "$health_status" == "unhealthy" || "$health_status" == "exited" || "$attempt" == "60" ]]; then
      echo "The $service service did not become healthy." >&2
      "${COMPOSE[@]}" logs --tail=150 "$service" >&2
      exit 1
    fi

    sleep 1
  done
done

backend_address="$("${COMPOSE[@]}" port backend 5000)"

printf '
Matcha is ready:
'
printf '  Frontend: http://localhost:3000
'
printf '  Backend:  http://%s
' "$backend_address"
printf '  Seed:     seed_001 through seed_500
'
