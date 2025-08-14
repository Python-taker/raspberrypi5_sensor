#!/usr/bin/env bash
# 전체 프로젝트 스냅샷(코드 + 설정 파일) 백업
# 사용: bash scripts/backup.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${HOME}/backups"
STAMP="$(date +'%Y%m%d_%H%M%S')"
NAME="ssafy_project_${STAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

echo "📦 백업 생성: ${BACKUP_DIR}/${NAME}"
# 불필요물 제외: __pycache__, .git, .venv 등
tar --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='.venv' \
    -czf "${BACKUP_DIR}/${NAME}" -C "${PROJECT_DIR}/.." "ssafy_project"

echo "✅ 완료: ${BACKUP_DIR}/${NAME}"
ls -lh "${BACKUP_DIR}/${NAME}"
