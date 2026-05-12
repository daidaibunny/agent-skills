#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${1:-$(pwd)}"
PROXY_ADDR="${PROXY_ADDR:-http://127.0.0.1:10808}"

cd "$WORKDIR"

export http_proxy="$PROXY_ADDR"
export https_proxy="$PROXY_ADDR"

git push origin "$(git branch --show-current)"
