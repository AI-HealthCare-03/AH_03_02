#!/usr/bin/env bash
# models/ckd predictor를 tar.gz로 패키징 (Google Drive 업로드용).
# 새 모델을 학습한 사람이 팀에 배포할 때 실행.
#
# 사용:
#   ./scripts/setup/dump_models.sh [출력파일명]
set -euo pipefail
cd "$(dirname "$0")/../.."  # 코드 루트로 이동

OUT="${1:-models_ckd.tar.gz}"

if [ ! -d models/ckd ]; then
  echo "❌ models/ckd 가 없습니다. 먼저 학습(src.ckd.train)하거나 받으세요."
  exit 1
fi

echo "📦 models/ckd → $OUT (수 GB·수 분 소요)..."
tar czf "$OUT" -C models ckd

echo "✅ 완료: $OUT ($(du -sh "$OUT" | cut -f1))"
echo "   → Google Drive에 업로드하고 공유 링크의 file ID를 팀에 전달하세요."
echo "   받는 쪽: MODELS_GDRIVE_ID=<id> ./scripts/setup/fetch_models.sh"
