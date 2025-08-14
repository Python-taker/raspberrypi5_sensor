#!/usr/bin/env bash
# 최신 백업을 프로젝트 상위에 풀기
# 사용: bash scripts/restore.sh

set -euo pipefail
BACKUP_DIR="${HOME}/backups"
LATEST="$(ls -t ${BACKUP_DIR}/ssafy_project_*.tar.gz | head -n1)"

if [[ -z "${LATEST}" ]]; then
  echo "❌ 백업 파일이 없습니다: ${BACKUP_DIR}"
  exit 1
fi

echo "🧩 복원: ${LATEST}"
tar -xzf "${LATEST}" -C "${HOME}"
echo "✅ 복원 완료: ~/ssafy_project"
