"""챌린지 트랙·카테고리 메타상수 + 트랙 자동배정 (순수 모듈, DB 의존 없음).

팀원 제공 설계(ckd-challenge.html + 챌린지 구성.pdf) 기준.
app_group 규약: A/B/C/D (clinical_reference.M1_GROUP_TITLE와 동일).
REQUIRED_CHECKLIST 출처: docs/reference/challenge/ckd-challenge.html 각 트랙 required 배열.
"""

from app.models.challenge import ChallengeTrack

# ──────────────────────────────────────────────────────────────────────────────
# 트랙 라벨
# ──────────────────────────────────────────────────────────────────────────────

TRACK_LABEL = {
    "DIALYSIS": "투석·이식 트랙",
    "CKD": "비투석 CKD 트랙",
    "INTENSIVE": "집중케어 트랙",
    "DAILY": "일상케어 트랙",
    "WELLNESS": "웰니스 트랙",
}

# ──────────────────────────────────────────────────────────────────────────────
# 카테고리 라벨
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_LABEL = {
    "HYDRATION": "수분",
    "DIET": "식단",
    "EXERCISE": "운동",
    "SLEEP": "수면",
    "STRESS": "스트레스",
    "EDUCATION": "교육·이해",
    "RECORD": "기록 습관",
    "MONITORING": "검사·수치 관리",
    "EMOTION": "정서",
}

# ──────────────────────────────────────────────────────────────────────────────
# 스테이지 라벨
# ──────────────────────────────────────────────────────────────────────────────

STAGE_LABEL = {1: "잔디", 2: "산스장", 3: "헬스장", 4: "지옥도"}

# ──────────────────────────────────────────────────────────────────────────────
# 트랙 → 카테고리 목록 (UI 탭 순서)
# 투석/CKD 트랙: 교육·기록·검사·운동·정서
# 집중케어/일상케어/웰니스 트랙: 수분·식단·운동·수면·스트레스
# ──────────────────────────────────────────────────────────────────────────────

TRACK_CATEGORIES: dict[str, list[str]] = {
    "DIALYSIS": ["EDUCATION", "RECORD", "MONITORING", "EXERCISE", "EMOTION"],
    "CKD": ["EDUCATION", "RECORD", "MONITORING", "EXERCISE", "EMOTION"],
    "INTENSIVE": ["HYDRATION", "DIET", "EXERCISE", "SLEEP", "STRESS"],
    "DAILY": ["HYDRATION", "DIET", "EXERCISE", "SLEEP", "STRESS"],
    "WELLNESS": ["HYDRATION", "DIET", "EXERCISE", "SLEEP", "STRESS"],
}

# ──────────────────────────────────────────────────────────────────────────────
# 트랙 → 매일 필수 체크리스트 [(item_key, 문구)]
# 출처: docs/reference/challenge/ckd-challenge.html TRACKS.<track>.required 배열
# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_CHECKLIST: dict[str, list[tuple[str, str]]] = {
    "DIALYSIS": [
        ("medication", "[복약] 처방약을 정해진 시간 내로 복용하셨나요?"),
        ("diet_fluid", "[식이·수분] 주치의가 처방한 수분 제한량 및 식이요법(칼륨, 인 등)을 지키셨나요?"),
        ("appointment", "[투석 일정] 캘린더에 투석 일정이 등록되어 있나요?"),
        ("symptom", "[이상 증상] 호흡곤란·심한 부종 등 이상 시 즉시 의료진에게 연락하세요."),
    ],
    "CKD": [
        ("medication", "[복약] 처방약을 정해진 시간 내로 복용하셨나요?"),
        ("diet_fluid", "[식이·수분] 주치의가 정한 수분·식이 지키셨나요?"),
        ("appointment", "[진료·검사] 진료 예약일을 캘린더에 등록되어 있나요?"),
        ("symptom", "[이상 증상] 부종, 소변량, 체중 이상 시 즉시 의료진에게 연락하세요."),
    ],
    "INTENSIVE": [
        ("hydration", "[수분] 아침 식사 전 물 한 잔(200 mL) 마시기"),
        ("diet", "[식단] 오늘 국·찌개를 먹을 때 국물을 절반 이상 남기기"),
        ("exercise", "[운동] 오늘 10분 이상 걷기"),
        ("sleep", "[수면] 오늘 취침 30분 전 스마트폰·태블릿을 내려놓기"),
    ],
    "DAILY": [
        ("hydration", "[수분] 아침 식사 전 물 한 잔(200 mL) 마시기"),
        ("diet", "[식단] 오늘 아침·점심·저녁 3끼를 거르지 않고 규칙적인 시간에 먹기"),
        ("exercise", "[운동] 오늘 10분 이상 걷기"),
        ("sleep", "[수면] 오늘 취침 30분 전 스마트폰·태블릿을 내려놓기"),
    ],
    "WELLNESS": [
        ("hydration", "[수분] 아침 식사 전 물 한 잔(200 mL) 마시기"),
        ("diet", "[식단] 오늘 채소가 포함된 식사를 1끼 이상 하기"),
        ("exercise", "[운동] 오늘 10분 이상 걷기"),
        ("sleep", "[수면] 오늘 취침 30분 전 스마트폰·태블릿을 내려놓기"),
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────────────────────────────────────


def m_track_label(track: str) -> str:
    """트랙 키 → 한글 라벨 반환."""
    return TRACK_LABEL.get(track, track)


def category_label(category: str) -> str:
    """카테고리 키 → 한글 라벨 반환."""
    return CATEGORY_LABEL.get(category, category)


def stage_label(stage: int) -> str:
    """스테이지 번호 → 한글 라벨 반환."""
    return STAGE_LABEL.get(stage, str(stage))


# ──────────────────────────────────────────────────────────────────────────────
# 트랙 자동배정
# ──────────────────────────────────────────────────────────────────────────────


def assign_track(
    app_group: str | None,
    ckd_diagnosed: bool,
    dialysis_type: str | None = None,
) -> ChallengeTrack:
    """CKD 진단 여부·dialysis_type·앱 그룹(A/B/C/D)으로 트랙을 자동배정.

    트랙은 자동 배정되며 사용자가 변경할 수 없다.
    app_group(대시보드 그룹)과 동일하게 dialysis_type으로 투석/비투석을 판정한다.

    배정 순서 (우선순위):
    1. CKD 진단자 — 진단=예면 무조건 분기, 스크리닝(2단계)으로 내려가지 않음
       - 혈액투석/복막투석/이식 → DIALYSIS 트랙 (투석·이식, 의료진 배정)
       - 그 외(비투석·미입력)  → CKD 트랙 (비투석 보존기, 의료진 배정)
    2. 미진단자 스크리닝 (서비스 관리 대상)
       - A 그룹 (신장 집중 관리군)   → INTENSIVE 트랙
       - B·C 그룹 (위험·사전 관리군) → DAILY 트랙
       - D 그룹 또는 미분류           → WELLNESS 트랙 (fallback)
    """
    if ckd_diagnosed:
        # 투석/이식 → DIALYSIS, 그 외(비투석·미입력)는 비투석 보존기 CKD.
        if dialysis_type in ("hemodialysis", "peritoneal", "transplant"):
            return ChallengeTrack.DIALYSIS
        return ChallengeTrack.CKD

    # 미진단 = 서비스 관리 대상 (app_group 기반 배정)
    if app_group == "A":
        return ChallengeTrack.INTENSIVE
    if app_group in ("B", "C"):
        return ChallengeTrack.DAILY
    # D 그룹 또는 검진 전 미분류 기본값(fallback)
    return ChallengeTrack.WELLNESS
