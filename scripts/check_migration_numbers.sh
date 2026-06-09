#!/usr/bin/env bash
# 마이그레이션 정수 prefix 중복 검사 (병렬 브랜치 충돌 방지).
#
# 배경: aerich는 `N_타임스탬프_이름.py`에서 N(정수)을 "기존 최대값+1"로 자동 생성한다.
#       두 사람이 동시에 같은 develop을 기준으로 마이그를 만들면 둘 다 같은 N을 받아
#       머지 시 번호가 겹친다. aerich는 파일명 전체로 추적해 적용 자체는 정상이지만,
#       다음 `aerich migrate`가 헛 마이그를 만들 수 있어 신규 충돌은 PR 단계에서 막는다.
#
# 충돌 PR 해결법: 최신 develop에 rebase → 겹치는 마이그 파일 삭제 → `aerich migrate`로 재생성.
#
# grandfather: 25·26은 2026-06-09 병렬 머지(animal_skins ↔ ai_guide/dialysis_type)로 이미 충돌.
#              이미 머지된 마이그 번호 변경은 다른 DB의 aerich 버전테이블과 어긋나 더 위험하므로 예외 처리.
set -euo pipefail

DIR="app/core/db/migrations/models"
GRANDFATHERED=" 25 26 " # 앞뒤 공백으로 정확 매칭 (예: " 25 " ⊄ " 250 ")

dups=$(ls "$DIR" | grep -E '^[0-9]+_' | sed -E 's/^([0-9]+)_.*/\1/' | sort | uniq -d || true)

fail=0
for n in $dups; do
  if [[ "$GRANDFATHERED" == *" $n "* ]]; then
    echo "::warning::마이그 번호 $n 중복 (기존 grandfathered, 허용)"
  else
    echo "::error::마이그 번호 $n 가 중복입니다. 최신 develop에 rebase 후 'aerich migrate'로 재생성하세요."
    fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then
  echo "❌ 마이그 번호 중복 검사 실패"
  exit 1
fi
echo "✅ 마이그 번호 중복 검사 통과 (grandfathered: 25 26)"
