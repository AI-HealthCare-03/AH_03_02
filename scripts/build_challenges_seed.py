"""
HTML의 TRACKS JS 객체를 파싱해 challenges_v05.json 시드 파일로 변환하는 스크립트.

실행 방법:
  uv run python scripts/build_challenges_seed.py
"""

import json
import subprocess
import sys
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
HTML_PATH = PROJECT_ROOT / "docs/reference/challenge/ckd-challenge.html"
OUTPUT_PATH = PROJECT_ROOT / "src/ckd/data/challenges_v05.json"

# 트랙 키 매핑 (JS 키 → enum 값)
TRACK_MAP = {
    "dialysis": "DIALYSIS",
    "ckd": "CKD",
    "intensive": "INTENSIVE",
    "daily": "DAILY",
    "wellness": "WELLNESS",
}

# 카테고리 한글 → enum 매핑
CATEGORY_MAP = {
    "수분": "HYDRATION",
    "식단": "DIET",
    "운동": "EXERCISE",
    "수면": "SLEEP",
    "스트레스": "STRESS",
    "교육·이해": "EDUCATION",
    "기록 습관": "RECORD",
    "검사·수치 관리": "MONITORING",
    "정서": "EMOTION",
}

# 스테이지 문자열 → 정수 매핑
STAGE_MAP = {"S1": 1, "S2": 2, "S3": 3, "S4": 4}


def extract_tracks_block(html: str) -> str:
    """HTML에서 TRACKS JS 객체 블록을 추출한다."""
    # "const TRACKS = {" 시작 위치 탐색
    start_marker = "const TRACKS = {"
    start_idx = html.find(start_marker)
    if start_idx == -1:
        raise ValueError("HTML에서 'const TRACKS = {' 를 찾을 수 없습니다.")

    # TRACKS 객체의 끝 중괄호를 찾기 위해 중괄호 카운팅
    brace_count = 0
    end_idx = start_idx + len("const TRACKS = ")
    for i, ch in enumerate(html[start_idx + len("const TRACKS = ") :], start=end_idx):
        if ch == "{":
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break

    tracks_block = html[start_idx + len("const TRACKS = ") : end_idx]
    return tracks_block


def parse_tracks_with_node(tracks_block: str) -> dict:
    """node.js를 사용해 JS 객체 블록을 JSON으로 변환 후 파싱한다."""
    # node에 JS 블록을 전달해 JSON 직렬화
    node_script = f"const X = {tracks_block}; process.stdout.write(JSON.stringify(X));"
    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"node 실행 실패:\n{result.stderr}")
    return json.loads(result.stdout)


def build_records(tracks: dict) -> list[dict]:
    """파싱된 TRACKS dict로 시드 레코드 목록을 생성한다."""
    records = []

    for track_key, track_data in tracks.items():
        # 지원되지 않는 트랙 키는 건너뜀
        track_enum = TRACK_MAP.get(track_key)
        if track_enum is None:
            print(f"  경고: 알 수 없는 트랙 키 '{track_key}' — 건너뜀", file=sys.stderr)
            continue

        challenges = track_data.get("challenges", {})

        for stage_key, cat_dict in challenges.items():
            # 지원되지 않는 스테이지 키는 건너뜀
            stage_num = STAGE_MAP.get(stage_key)
            if stage_num is None:
                print(
                    f"  경고: 알 수 없는 스테이지 '{stage_key}' (트랙={track_key}) — 건너뜀",
                    file=sys.stderr,
                )
                continue

            for cat_name, texts in cat_dict.items():
                # 카테고리 한글 → enum 변환
                cat_enum = CATEGORY_MAP.get(cat_name)
                if cat_enum is None:
                    print(
                        f"  경고: 알 수 없는 카테고리 '{cat_name}' (트랙={track_key}, 스테이지={stage_key}) — 건너뜀",
                        file=sys.stderr,
                    )
                    continue

                for text in texts:
                    # 텍스트를 name(최대 200자)·description으로 사용
                    name = text[:200]
                    record = {
                        "track": track_enum,
                        "stage": stage_num,
                        "category": cat_enum,
                        "name": name,
                        "description": text,
                        "duration_days": 1,
                    }
                    records.append(record)

    return records


def main() -> None:
    print(f"HTML 파일 읽기: {HTML_PATH}")
    html = HTML_PATH.read_text(encoding="utf-8")

    print("TRACKS 블록 추출 중...")
    tracks_block = extract_tracks_block(html)

    print("node.js로 JS 객체 파싱 중...")
    tracks = parse_tracks_with_node(tracks_block)

    print("시드 레코드 생성 중...")
    records = build_records(tracks)

    # 출력 디렉토리 생성(이미 있으면 무시)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"JSON 저장: {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # 변환 결과 요약 출력
    from collections import Counter

    track_counts = dict(Counter(r["track"] for r in records))
    cat_counts = dict(Counter(r["category"] for r in records))

    print(f"\n변환 완료: 총 {len(records)}개")
    print("  트랙별:")
    for k, v in sorted(track_counts.items()):
        print(f"    {k}: {v}")
    print("  카테고리별:")
    for k, v in sorted(cat_counts.items()):
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
