#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

key_file=olimpiads_data_v2/openrouter.key
if [[ ! -s "$key_file" ]]; then
  echo "Нет ключа: $key_file" >&2
  exit 1
fi

python_bin=python3
if [[ -x .venv/bin/python ]]; then
  python_bin=.venv/bin/python
fi

exec "$python_bin" -u -m search.task_search --api-key-file "$key_file" index \
  --batch-size 32 --workers 8 "$@"
