#!/usr/bin/env bash
# 현재 venv/시스템의 pip 패키지를 requirements.txt로 동결
# 사용: bash scripts/freeze_deps.sh

set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 가상환경 권장 (예: python -m venv .venv && source .venv/bin/activate)
# 필요 시 시스템 전역으로도 동작하지만, venv 사용을 강력 권장
echo "📌 pip freeze → requirements.txt"
pip freeze | grep -vE '^(pip==|setuptools==|wheel==)$' > "${PROJECT_DIR}/requirements.txt"

echo "✅ 동결 완료: ${PROJECT_DIR}/requirements.txt"
tail -n +1 "${PROJECT_DIR}/requirements.txt" | sed -n '1,20p'
