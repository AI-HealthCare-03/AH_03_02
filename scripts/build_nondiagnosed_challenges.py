"""비진단자(A/B·C/D = INTENSIVE/DAILY/WELLNESS) 선택 챌린지를 PDF에서 추출해
challenges_v05.json의 비진단자 300개를 교체한다. 진단자(DIALYSIS/CKD) 200개는 보존.

SSOT: 팀 전달 PDF '챌린지 수정사항2.pdf' (A~D그룹 챌린지 정의서).
PDF 순서 = A그룹(INTENSIVE) → B·C그룹(DAILY) → D그룹(WELLNESS),
각 S1~S4, 각 수분·식단·운동·수면·스트레스 1~5 순서로 일관.

사용: python scripts/build_nondiagnosed_challenges.py <pdf경로>
"""

import json
import re
import sys
from pathlib import Path

import fitz  # pymupdf

CAT_MAP = {
    "수분": "HYDRATION",
    "식단": "DIET",
    "운동": "EXERCISE",
    "수면": "SLEEP",
    "스트레스": "STRESS",
}
TRACKS_ORDER = ["INTENSIVE", "DAILY", "WELLNESS"]  # PDF 순서 A → B·C → D
JSON_PATH = Path(__file__).resolve().parents[1] / "src/ckd/data/challenges_v05.json"


def extract_rows(pdf_path: str) -> list[tuple[str, int, str]]:
    """챌린지 표(헤더=카테고리/번호/챌린지 내용)에서 (카테고리, 번호, 내용)을 페이지순 수집."""
    doc = fitz.open(pdf_path)
    rows: list[tuple[str, int, str]] = []
    for pno in range(3, len(doc)):  # p4부터 (선택 챌린지 표 시작)
        for tab in doc[pno].find_tables().tables:
            data = tab.extract()
            if not data or (data[0][0] or "").strip() != "카테고리":
                continue  # 챌린지 표만 (단계정의·변경요약 표 제외)
            for r in data[1:]:
                cat = (r[0] or "").strip()
                num = (r[1] or "").strip()
                content = " ".join((r[2] or "").split())  # 멀티라인 셀 공백 정리
                # 줄바꿈 아티팩트: 닫는괄호 뒤 조사가 다음 줄로 wrap된 경우의 공백 제거(예: "이내) 을"→"이내)을")
                content = re.sub(r"\)\s+([을를이가은는의에])", r")\1", content)
                if cat in CAT_MAP and num.isdigit() and content:
                    rows.append((cat, int(num), content))
    return rows


def build_records(rows: list[tuple[str, int, str]]) -> list[dict]:
    """수집된 300행을 트랙·스테이지·카테고리(영문)로 매핑. 순서·개수·패턴을 강하게 검증."""
    assert len(rows) == 300, f"행 수 {len(rows)} != 300"
    exp_cats = ["수분"] * 5 + ["식단"] * 5 + ["운동"] * 5 + ["수면"] * 5 + ["스트레스"] * 5
    exp_nums = [1, 2, 3, 4, 5] * 5
    for i in range(0, 300, 25):
        chunk = rows[i : i + 25]
        assert [c for c, _, _ in chunk] == exp_cats, f"카테고리 패턴 불일치 @stage{i // 25}"
        assert [n for _, n, _ in chunk] == exp_nums, f"번호 패턴 불일치 @stage{i // 25}"

    recs: list[dict] = []
    for idx, (cat, _num, content) in enumerate(rows):
        track = TRACKS_ORDER[idx // 100]
        stage = (idx % 100) // 25 + 1
        recs.append(
            {
                "track": track,
                "stage": stage,
                "category": CAT_MAP[cat],
                "name": content,
                "description": content,
                "duration_days": 1,
            }
        )
    # stage 간 (track, category, name) 중복 방지 가드.
    # PDF의 특정 stage 칸에 이전 stage 문구가 복붙되면 화면에 같은 챌린지가
    # 중복 노출된다(2026-06-16 발견·수정: HYDRATION 알코올·카페인, SLEEP 취침 4건).
    # PDF를 재추출할 때 중복이 재유입되지 않도록 여기서 강하게 검증한다.
    from collections import Counter

    dup = {k: v for k, v in Counter((r["track"], r["category"], r["name"]) for r in recs).items() if v > 1}
    assert not dup, (
        f"stage 간 챌린지 중복 {len(dup)}건 — PDF의 해당 (track,category) 칸에 "
        "이전 stage와 동일한 문구가 들어 있습니다. 각 stage가 고유 챌린지가 되도록 "
        "PDF를 수정한 뒤 재실행하세요: " + "; ".join(f"{t}/{c}/{n[:18]}…(×{v})" for (t, c, n), v in dup.items())
    )
    return recs


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("사용: python scripts/build_nondiagnosed_challenges.py <pdf경로>")
    pdf_path = sys.argv[1]

    new_nondiag = build_records(extract_rows(pdf_path))

    existing = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    diag = [d for d in existing if d["track"] in ("DIALYSIS", "CKD")]
    assert len(diag) == 200, f"진단자(DIALYSIS/CKD) {len(diag)} != 200 — 기존 시드 확인 필요"

    merged = diag + new_nondiag
    JSON_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    from collections import Counter

    c = Counter(d["track"] for d in merged)
    print(f"완료: 진단자 {len(diag)} + 비진단자 {len(new_nondiag)} = {len(merged)}")
    for t in ["DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"]:
        print(f"  {t}: {c[t]}")


if __name__ == "__main__":
    main()
