#!/usr/bin/env bash
set -euo pipefail

xcode-select -p >/dev/null 2>&1 || xcode-select --install || true

command -v brew >/dev/null 2>&1 || { echo "Install Homebrew first."; exit 1; }

brew update
brew install python jq binutils coreutils p7zip

echo "[OK] Base packages installed."
echo "Next:"
echo "  make install"
echo "  make demo"
echo "  make run DIR=challenges/demo"
