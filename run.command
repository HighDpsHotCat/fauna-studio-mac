#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

if [[ ! -x .venv/bin/python ]]; then
    python_bin="${FAUNA_PYTHON:-python3.11}"
    if ! command -v "$python_bin" >/dev/null 2>&1; then
        printf '%s\n' 'Python 3.11을 설치한 뒤 다시 실행하세요.'
        printf '%s\n' '다른 Python 경로는 FAUNA_PYTHON 환경 변수로 지정할 수 있습니다.'
        exit 1
    fi
    "$python_bin" -m venv .venv
fi

.venv/bin/python - <<'PY'
import platform
import sys

if sys.platform != "darwin" or platform.machine() != "arm64":
    raise SystemExit("Mac 실행기는 Apple Silicon용 arm64 Python이 필요합니다. Rosetta 사용 여부를 확인하세요.")
if not (3, 10) <= sys.version_info[:2] <= (3, 11):
    raise SystemExit("이 개발 환경은 Python 3.10 또는 3.11로 실행하세요.")
PY

.venv/bin/python -X utf8 bootstrap.py
exec .venv/bin/python -X utf8 app.py "$@"
