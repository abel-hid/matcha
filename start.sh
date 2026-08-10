#!/usr/bin/env bash

echo "[1/5] Building backend and frontend"
docker compose --env-file backend/.env -f docker-compose.yml build backend frontend

echo
echo "[2/5] Starting PostgreSQL"
docker compose --env-file backend/.env -f docker-compose.yml up -d --wait db

echo
echo "[3/5] Applying database schema"
docker compose --env-file backend/.env -f docker-compose.yml run --rm schema

echo
echo "[4/5] Generating 500 evaluation profiles"
docker compose --env-file backend/.env -f docker-compose.yml run --rm seed

echo
echo "[5/5] Starting backend and frontend"
docker compose --env-file backend/.env -f docker-compose.yml up -d --wait backend frontend

echo
echo "Matcha is ready."
echo
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:5000"
echo "Profiles: seed_001 - seed_500"
echo "Password: lhfTYh6452fdHH9@"