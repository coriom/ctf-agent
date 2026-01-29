#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  git jq file binutils xxd unzip p7zip-full

echo "[OK] Base packages installed."
echo "Next:"
echo "  make install"
echo "  make demo"
echo "  make run DIR=challenges/demo"
