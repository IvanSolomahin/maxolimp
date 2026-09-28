#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 PREVIOUS_COMMIT CURRENT_COMMIT" >&2
  exit 2
fi

previous_commit=$1
current_commit=$2
frontend_changed=false
frontend_image_changed=false
task_changed=false
olymp_changed=false
compose_changed=false

build_with_retries() {
  local attempt=1
  local max_attempts=3
  local delay=5

  while true; do
    if docker compose build "$@"; then
      return 0
    fi
    if (( attempt >= max_attempts )); then
      echo "Docker build failed after $max_attempts attempts" >&2
      return 1
    fi
    echo "Docker build failed (attempt $attempt/$max_attempts); retrying in ${delay}s" >&2
    sleep "$delay"
    attempt=$((attempt + 1))
    delay=$((delay * 2))
  done
}

while IFS= read -r -d '' path; do
  case "$path" in
    docker-compose.yml) compose_changed=true ;;
    ui/public/*) frontend_changed=true ;;
    ui/Dockerfile|ui/nginx.conf) frontend_image_changed=true ;;
    task_find_service/*) task_changed=true ;;
    olymp_find_service/*) olymp_changed=true ;;
  esac
done < <(git diff --no-renames --name-only -z "$previous_commit" "$current_commit")

if [[ $compose_changed == true ]]; then
  echo "docker-compose.yml changed; updating the full stack"
  build_with_retries
  docker compose up -d --no-build
  exit
fi

services=()
if [[ $frontend_image_changed == true ]]; then
  services+=(frontend)
elif [[ $frontend_changed == true ]]; then
  echo "Static frontend files updated through the live-mounted ui/public directory; no container restart needed"
fi
[[ $task_changed == true ]] && services+=(task-app)
[[ $olymp_changed == true ]] && services+=(olymp-app)

if (( ${#services[@]} == 0 )); then
  echo "No container changes; deployment skipped"
  exit
fi

echo "Updating: ${services[*]}"
build_with_retries "${services[@]}"
docker compose up -d --no-build --no-deps "${services[@]}"
