#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export AI_TRAINER_PYTHON_PATH="$PWD/core/python"
# Use one matching interpreter, headers and library for real in-process desktop tests.
PYTHON_CONFIG="${PYTHON_CONFIG:-python3-config}"
export AI_TRAINER_PYTHON_HOME="$("$PYTHON_CONFIG" --prefix)"
PYTHONPATH=core/python python3 -m unittest discover -s core/python/tests -v
flags=()
for flag in $("$PYTHON_CONFIG" --includes); do flags+=(-Xcc "$flag"); done
for flag in $("$PYTHON_CONFIG" --embed --ldflags); do flags+=(-Xlinker "$flag"); done
flags+=(-Xlinker -L"$AI_TRAINER_PYTHON_HOME/lib" -Xlinker -rpath -Xlinker "$AI_TRAINER_PYTHON_HOME/lib")
swift test "${flags[@]}"
