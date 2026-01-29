#!/usr/bin/env bash
set -euo pipefail

DIR="${1:-}"
[ -n "$DIR" ] || { echo "Usage: scripts/run_docker.sh challenges/demo"; exit 2; }

docker build -t ctf-agent:local .

# no-network, read-only challenge mount
docker run --rm -it \
  --network none \
  -v "$(pwd)/$DIR:/input:ro" \
  -v "$(pwd)/artifacts:/artifacts:rw" \
  ctf-agent:local \
  ctf-agent solve /input --out /artifacts/latest --work /artifacts/work
