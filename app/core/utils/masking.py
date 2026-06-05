"""관리자 페이지 PHI/PII 마스킹 유틸 (CLAUDE.md §5 정책).

원본을 직접 노출하지 않고 가명화 표시한다. 검색·필터링은 가능하되 화면에는 마스킹 적용.

마스킹 규칙:
- 이메일: 로컬파트 앞 2글자 + *** + @도메인  (예: ki***@gmail.com)
- 이름  : 첫 글자 + ** (예: 홍**)
- 전화  : 가운데 4자리 마스킹 (예: 010-****-1234)
- 혈압·혈당 등 검진 수치: 정확값 X, 범주 라벨로 변환 (예: 정상범위 / 경계 / 주의)
"""

from __future__ import annotations


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def mask_name(name: str | None) -> str | None:
    if not name:
        return name
    if len(name) <= 1:
        return f"{name}*"
    return f"{name[:1]}{'*' * (len(name) - 1)}"


def mask_phone(phone: str | None) -> str | None:
    """01012345678 → 010-****-5678 / 0212345678 → 02-****-5678"""
    if not phone:
        return phone
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}-****-{digits[-4:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-***-{digits[-4:]}"
    return "*" * len(phone)


# ── 검진 수치 범주화 ─────────────────────────────────
def categorize_systolic_bp(value: int | float | None) -> str:
    """KDIGO·고혈압학회 권고 기준으로 범주화."""
    if value is None:
        return "데이터 없음"
    if value < 120:
        return "정상"
    if value < 130:
        return "주의(고혈압 전단계)"
    if value < 140:
        return "고혈압 1단계"
    if value < 180:
        return "고혈압 2단계"
    return "고위험(즉시 의료기관 권고)"


def categorize_fasting_glucose(value: int | float | None) -> str:
    if value is None:
        return "데이터 없음"
    if value < 100:
        return "정상"
    if value < 126:
        return "공복혈당장애(전당뇨)"
    if value < 200:
        return "당뇨 의심"
    return "고위험(즉시 의료기관 권고)"


def categorize_egfr(value: int | float | None) -> str:
    if value is None:
        return "데이터 없음"
    if value >= 90:
        return "G1 · 정상"
    if value >= 60:
        return "G2 · 경계"
    if value >= 45:
        return "G3a · 경증"
    if value >= 30:
        return "G3b · 중등"
    if value >= 15:
        return "G4 · 중증"
    return "G5 · 신부전(고위험)"
