#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
WORKSPACE_OPERATION=Bootstrap exec "$SCRIPT_DIR/restore-repos.sh" "$@"
