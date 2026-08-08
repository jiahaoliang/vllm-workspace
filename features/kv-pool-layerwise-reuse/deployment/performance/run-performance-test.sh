#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly workspace_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
export VLLM_WORKSPACE_ROOT="${workspace_root}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$(dirname -- "${script_dir}")${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m performance.runner "$@"
