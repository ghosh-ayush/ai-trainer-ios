#!/bin/bash
# Development-time download only. No downloading or network access occurs in the app.
set -euo pipefail
cd "$(dirname "$0")/.."
archive="${1:-/tmp/AITrainer-Python-3.13-iOS-support.b13.tar.gz}"
if [ ! -f "$archive" ]; then
    curl --fail --location --output "$archive" https://github.com/beeware/Python-Apple-support/releases/download/3.13-b13/Python-3.13-iOS-support.b13.tar.gz
fi
expected=d1f95f95137a4b91dc0cbe9b99ddfc0a78918dde883c7fbe7147074a5e715274
actual=$(shasum -a 256 "$archive" | cut -d ' ' -f 1)
[ "$actual" = "$expected" ] || { echo "Python runtime checksum mismatch" >&2; exit 1; }
mkdir -p apps/ios/Vendor
tar -xzf "$archive" -C apps/ios/Vendor
