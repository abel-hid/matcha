#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

step() {
  printf '\n[%s/7] %s\n' "$1" "$2"
}

fail() {
  printf '\nERROR: %s\n' "$1" >&2
  exit 1
}

on_error() {
  printf '\nStartup stopped at line %s. Review the error above.\n' "$1" >&2
}
trap 'on_error "$LINENO"' ERR

if (( $# != 0 )); then
  fail 'Usage: ./start.sh'
fi

step 1 'Checking local requirements'
command -v docker >/dev/null 2>&1 || fail 'Docker is required.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose is required.'
[[ -f backend/.env ]] || fail 'backend/.env is missing. Run: cp backend/.env.example backend/.env'

COMPOSE=(docker compose --env-file backend/.env -f docker-compose.yml)
"${COMPOSE[@]}" config --quiet
printf 'Configuration is valid.\n'

step 2 'Building backend and frontend images'
"${COMPOSE[@]}" build backend frontend
"${COMPOSE[@]}" run --rm --no-deps backend python -c   "from app.config import Config; Config.validate(); print('Backend configuration is valid.')"

step 3 'Starting PostgreSQL'
"${COMPOSE[@]}" up -d db
for attempt in $(seq 1 40); do
  if "${COMPOSE[@]}" exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    printf 'PostgreSQL is ready.\n'
    break
  fi
  if (( attempt == 40 )); then
    "${COMPOSE[@]}" logs --tail=100 db >&2
    fail 'PostgreSQL did not become ready.'
  fi
  sleep 1
done

step 4 'Applying the database schema'
"${COMPOSE[@]}" run --rm schema

step 5 'Generating exactly 500 evaluation profiles'
"${COMPOSE[@]}" run --rm seed

step 6 'Starting the API, Socket.IO, and Next.js services'
"${COMPOSE[@]}" up -d backend frontend

step 7 'Waiting for service health checks'
for service in backend frontend; do
  container_id="$("${COMPOSE[@]}" ps -q "$service")"
  [[ -n "$container_id" ]] || fail "The $service container was not created."

  for attempt in $(seq 1 60); do
    health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
    if [[ "$health_status" == 'healthy' ]]; then
      printf '%-10s healthy\n' "$service"
      break
    fi
    if [[ "$health_status" == 'unhealthy' || "$health_status" == 'exited' || "$attempt" == '60' ]]; then
      "${COMPOSE[@]}" logs --tail=150 "$service" >&2
      fail "The $service service did not become healthy."
    fi
    sleep 1
  done
done

printf '\nMatcha is ready for local testing.\n'
printf '  Frontend: http://localhost:3000\n'
printf '  Backend:  http://localhost:5000\n'
printf '  Profiles: seed_001 through seed_500\n'
printf '  Password: lhfTYh6452fdHH9@\n'
printf '  Logs:     docker compose --env-file backend/.env logs -f backend frontend\n\n'
