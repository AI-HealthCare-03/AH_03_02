#!/usr/bin/env bash
# CKD predictor(models/ckd)를 Google Drive에서 다운로드 → 압축 해제.
# git에 올라가지 않는 대용량 모델(~5.3GB)을 받는 쪽 스크립트.
#
# 사용:
#   MODELS_GDRIVE_ID=<file_id> ./scripts/setup/fetch_models.sh
#
# file_id 는 Google Drive 공유 링크 .../file/d/<FILE_ID>/view 의 가운데 부분.
set -euo pipefail
cd "$(dirname "$0")/../.."  # 코드 루트로 이동

GDRIVE_ID="${MODELS_GDRIVE_ID:-}"
FILE="models_ckd.tar.gz"

if [ -z "$GDRIVE_ID" ]; then
  echo "❌ MODELS_GDRIVE_ID 환경변수가 필요합니다."
  echo "   예: MODELS_GDRIVE_ID=1AbC... ./scripts/setup/fetch_models.sh"
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "⬇️  Google Drive에서 모델 다운로드 (gdown)..."
  uvx gdown "$GDRIVE_ID" -O "$FILE"
fi

echo "📦 압축 해제 → models/ckd ..."
mkdir -p models
tar xzf "$FILE" -C models   # 아카이브가 ckd/ 를 담고 있다고 가정 → models/ckd/

echo "✅ 완료: models/ckd ($(du -sh models/ckd 2>/dev/null | cut -f1))"
echo "   (다운로드 파일 $FILE 은 필요 없으면 삭제해도 됩니다)"
