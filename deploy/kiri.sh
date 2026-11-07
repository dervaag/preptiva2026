#!/bin/sh
set -eu
deploy_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$deploy_root"

command_name=${1:-help}
if [ "$#" -gt 0 ]; then shift; fi
case "$command_name" in
  config|up)
    python3 deploy/configure_kiri.py
    ;;
  ps|logs|stop|down|exec)
    if [ ! -f .env.kiri ]; then
      printf '%s\n' 'Jalankan sh deploy/kiri.sh config terlebih dahulu.' >&2
      exit 1
    fi
    ;;
  *)
    printf '%s\n' 'Pemakaian: sh deploy/kiri.sh {config|up|ps|logs|stop|down|exec}'
    exit 0
    ;;
esac

# Explicit context prevents accidentally targeting Docker Desktop or a remote VM.
compose() {
  docker --context kiri compose --project-name preptiva --env-file .env --env-file .env.kiri -f compose.kiri.yaml "$@"
}
case "$command_name" in
  config) compose config --quiet ;;
  up) compose up -d --build --wait --wait-timeout 180 ;;
  ps) compose ps ;;
  logs) compose logs --tail=100 -f "$@" ;;
  stop) compose stop ;;
  down) compose down ;;
  exec) compose exec "$@" ;;
esac
