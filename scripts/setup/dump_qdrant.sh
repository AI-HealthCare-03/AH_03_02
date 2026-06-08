#!/usr/bin/env bash
# qdrant 벡터DB 볼륨을 tar.gz로 패키징 (Google Drive 업로드용).
# 인덱싱(run_indexing)을 마친 사람이 팀에 배포할 때 실행.
#
# 볼륨 전체를 복사하므로 일관성을 위해 qdrant를 잠시 중지한다.
#
# 사용:
#   ./scripts/setup/dump_qdrant.sh [출력파일명]
set -euo pipefail
cd "$(dirname "$0")/../.."  # 코드 루트로 이동

OUT="${1:-qdrant_snapshot.tar.gz}"

# 프로젝트 종속 볼륨명 자동 탐지 (template 볼륨 제외)
VOL=$(docker volume ls --format '{{.Name}}' | grep -E '_qdrant_data$' | grep -v template | head -1)
if [ -z "$VOL" ]; then
  echo "❌ qdrant 볼륨(*_qdrant_data)을 찾을 수 없습니다. 'docker compose up -d qdrant' 후 다시 실행하세요."
  exit 1
fi
echo "🔎 볼륨: $VOL"

echo "⏸️  qdrant 중지 (일관성 보장)..."
docker compose stop qdrant

echo "📦 볼륨 → $OUT ..."
docker run --rm -v "$VOL":/data:ro -v "$(pwd)":/backup alpine \
  tar czf "/backup/$OUT" -C /data .

echo "▶️  qdrant 재시작..."
docker compose start qdrant

echo "✅ 완료: $OUT ($(du -sh "$OUT" | cut -f1))"
echo "   → Google Drive에 업로드하고 file ID를 팀에 전달하세요."
echo "   받는 쪽: QDRANT_GDRIVE_ID=<id> ./scripts/setup/restore_qdrant.sh"
