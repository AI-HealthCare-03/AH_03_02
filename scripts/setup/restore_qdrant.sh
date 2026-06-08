#!/usr/bin/env bash
# qdrant 벡터DB를 Google Drive에서 다운로드 → 볼륨 복원.
# git에 올라가지 않는 벡터DB(~789MB)를 받는 쪽 스크립트.
#
# ⚠️ 기존 qdrant 볼륨 내용을 덮어씁니다. 처음 셋업할 때만 사용하세요.
#
# 사용:
#   QDRANT_GDRIVE_ID=<file_id> ./scripts/setup/restore_qdrant.sh
set -euo pipefail
cd "$(dirname "$0")/../.."  # 코드 루트로 이동

GDRIVE_ID="${QDRANT_GDRIVE_ID:-}"
FILE="qdrant_snapshot.tar.gz"

if [ -z "$GDRIVE_ID" ]; then
  echo "❌ QDRANT_GDRIVE_ID 환경변수가 필요합니다."
  echo "   예: QDRANT_GDRIVE_ID=1AbC... ./scripts/setup/restore_qdrant.sh"
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "⬇️  Google Drive에서 벡터DB 다운로드 (gdown)..."
  uvx gdown "$GDRIVE_ID" -O "$FILE"
fi

VOL=$(docker volume ls --format '{{.Name}}' | grep -E '_qdrant_data$' | grep -v template | head -1)
if [ -z "$VOL" ]; then
  echo "❌ qdrant 볼륨(*_qdrant_data)을 찾을 수 없습니다. 'docker compose up -d qdrant' 후 다시 실행하세요."
  exit 1
fi
echo "🔎 볼륨: $VOL"

echo "⏸️  qdrant 중지..."
docker compose stop qdrant

echo "♻️  볼륨 복원 (기존 내용 덮어씀)..."
docker run --rm -v "$VOL":/data -v "$(pwd)":/backup alpine \
  sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf /backup/$FILE -C /data"

echo "▶️  qdrant 재시작..."
docker compose start qdrant

echo "✅ 완료: qdrant 벡터DB 복원됨."
echo "   (다운로드 파일 $FILE 은 필요 없으면 삭제해도 됩니다)"
