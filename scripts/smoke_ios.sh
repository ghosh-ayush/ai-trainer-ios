#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
device_id="${1:?Pass a booted simulator UUID}"
app_path="${2:-DerivedData/Build/Products/Debug-iphonesimulator/AITrainer.app}"
xcrun simctl install "$device_id" "$app_path"
container=$(xcrun simctl get_app_container "$device_id" com.ghoshayush.AITrainer data)
result="$container/Documents/core-smoke-result.json"
rm -f "$result"
xcrun simctl launch --terminate-running-process "$device_id" com.ghoshayush.AITrainer --core-smoke-test
python3 - "$result" <<'PY'
import json, sys, time
from pathlib import Path
path = Path(sys.argv[1])
for _ in range(80):
    if path.exists(): break
    time.sleep(0.25)
else: raise SystemExit('No smoke result within 20 seconds; inspect simulator crash logs.')
result = json.loads(path.read_text())
print(json.dumps(result, indent=2))
if not result.get('passed'): raise SystemExit(1)
PY
