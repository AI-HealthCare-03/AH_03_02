"""Clova OCR 서비스 — 검진 결과지 이미지 → 텍스트·신뢰도 추출.

NAVER Clova OCR General API를 multipart/form-data로 호출하고 응답 JSON에서
fields[].inferText·inferConfidence만 추려 깔끔한 dict로 반환한다.

외부 API 오류·키 미설정·타임아웃·인증 실패는 모두 한국어 detail의 HTTPException으로 변환.
원본 상태 코드·응답 본문은 로그에만 남기고 사용자 응답에는 노출하지 않는다.
"""

import io
import json
import os
import re
import time
import uuid

import httpx
from fastapi import HTTPException, status
from pypdf import PdfReader, PdfWriter

from app.core.logger import setup_logger

logger = setup_logger("ocr_service")

_CLOVA_TIMEOUT_SEC = 30.0

# content_type → Clova format 매핑
_MIME_TO_FORMAT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "application/pdf": "pdf",
}

# 신뢰도 임계값 — 이 미만은 사용자 검토 권장 (low_confidence_count로 합산)
_LOW_CONFIDENCE_THRESHOLD = 0.85

# ManualInputPage form 필드 → 키워드 매핑.
# LDL은 시스템에서 사용하지 않으므로 제외.
# HDL은 _FIELD_KEYWORDS에서 빠짐 — 라인 그룹화가 HDL 행과 다른 행을 잘못 묶을 때
# 라인 매핑이 잘못된 숫자(예: HDL=120=중성지방 값)를 매핑하는 경로 차단.
# HDL은 _fallback_hdl_strict_row(옵션 D)가 셀 경계 기반으로 정확히 매핑.
_FIELD_KEYWORDS: list[tuple[str, list[str]]] = [
    ("fasting_glucose", ["공복혈당", "혈당", "glucose"]),
    ("creatinine", ["크레아티닌", "creatinine"]),
    ("total_cholesterol", ["총콜레스테롤", "총 콜레스테롤", "콜레스테롤"]),
    ("triglycerides", ["중성지방", "트리글리세라이드"]),
    ("systolic_bp", ["수축기", "최고혈압"]),
    ("diastolic_bp", ["이완기", "최저혈압"]),
    ("height", ["신장", "키"]),
    ("weight", ["체중", "몸무게"]),
    ("waist_circumference", ["허리둘레", "허리"]),
]

# 혈압 "130/85" 패턴
_BP_PATTERN = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})")
# 키+몸무게 슬래시 패턴 "172 / 68" (소수 허용)
_PAIR_PATTERN = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*/\s*(\d{2,3}(?:\.\d+)?)")
# 숫자 (천단위 콤마·소수 허용) — "1,200"·"118"·"0.9". 콤마버전을 우선 매칭.
_NUMBER_PATTERN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def _to_float(s: str) -> float:
    """천단위 콤마를 제거하고 float 변환. '1,200'→1200.0, '118'→118.0 (중성지방 등 4자리+ 값 오류 방지)."""
    return float(s.replace(",", ""))


# 판정·체크박스·정상범위 표현 — 이런 라인은 진짜 라벨이 아니라 정상/의심 판정·설명이라
# 키워드 매칭에서 제외 (예: "□ 낮은 고밀도 콜레스테롤 의심"이 진짜 라벨 가로채는 문제 차단).
_RULING_WORDS = (
    "□",
    "■",  # 체크박스
    "정상",
    "의심",
    "필요",
    "주의",
    "없음",
    "비해당",
    "유질환자",
    "전단계",
    "낮은",
    "고위험",
    "이상자",
    "장애",
    "고콜레스테롤혈증",
    "고중성지방혈증",
)

# 파일 매직 바이트 — content_type만 신뢰하지 않고 실제 파일 시그니처 검증
# (사용자가 docx를 .pdf로 잘못 저장한 케이스 등을 친절한 한국어 에러로 변환)
_PDF_MAGIC = b"%PDF-"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _group_by_linebreak(fields_raw: list[dict]) -> list[dict]:
    """lineBreak fallback 그룹화. boundingPoly 없는 응답용."""
    lines: list[dict] = []
    cur_texts: list[str] = []
    cur_conf: float = 1.0
    for f in fields_raw:
        text = (f.get("inferText") or "").strip()
        if not text:
            continue
        conf = float(f.get("inferConfidence") or 0.0)
        cur_texts.append(text)
        cur_conf = min(cur_conf, conf)
        if f.get("lineBreak"):
            lines.append({"text": " ".join(cur_texts), "confidence": round(cur_conf, 3)})
            cur_texts = []
            cur_conf = 1.0
    if cur_texts:
        lines.append({"text": " ".join(cur_texts), "confidence": round(cur_conf, 3)})
    return lines


def _extract_token_items(fields_raw: list[dict]) -> list[dict]:
    """boundingPoly에서 토큰별 좌표·텍스트 추출. 하나라도 polygon이 없으면 빈 리스트."""
    items: list[dict] = []
    for f in fields_raw:
        text = (f.get("inferText") or "").strip()
        if not text:
            continue
        poly = (f.get("boundingPoly") or {}).get("vertices") or []
        if len(poly) < 4:
            return []
        ys = [float(v.get("y", 0)) for v in poly]
        xs = [float(v.get("x", 0)) for v in poly]
        items.append(
            {
                "text": text,
                "conf": float(f.get("inferConfidence") or 0.0),
                "y_top": min(ys),
                "y_bot": max(ys),
                "y_mid": (min(ys) + max(ys)) / 2,
                "x": min(xs),
            }
        )
    return items


def _group_into_lines(fields_raw: list[dict]) -> list[dict]:
    """boundingPoly y좌표로 같은 표 행 토큰을 묶고 x좌표로 정렬해 라인 단위로 반환.

    Clova V2가 lineBreak를 토큰마다 발화해 라인 그룹화가 무력화되는 케이스가 많아
    좌표 기반으로 재그룹화한다. y범위가 절반 이상 겹치면 같은 줄로 판정.
    boundingPoly가 없는 응답은 lineBreak fallback.
    """
    items = _extract_token_items(fields_raw)
    if not items:
        return _group_by_linebreak(fields_raw)
    items.sort(key=lambda it: it["y_mid"])
    grouped: list[list[dict]] = [[items[0]]]
    # 같은 줄 판정: 그룹 평균 y_mid 와 토큰 y_mid 차이가 평균 토큰 높이의 절반 이내
    # (누적으로 y범위가 늘어나 다른 행까지 흡수되는 문제 방지)
    for it in items[1:]:
        last_group = grouped[-1]
        avg_mid = sum(c["y_mid"] for c in last_group) / len(last_group)
        avg_h = sum(c["y_bot"] - c["y_top"] for c in last_group) / len(last_group)
        tol = max(avg_h * 0.5, (it["y_bot"] - it["y_top"]) * 0.5)
        if tol > 0 and abs(it["y_mid"] - avg_mid) <= tol:
            last_group.append(it)
        else:
            grouped.append([it])
    out: list[dict] = []
    for g in grouped:
        g.sort(key=lambda c: c["x"])
        out.append(
            {
                "text": " ".join(c["text"] for c in g),
                "confidence": round(min(c["conf"] for c in g), 3),
            }
        )
    return out


def _try_map_blood_pressure(text: str, conf: float, mapped: dict[str, dict]) -> bool:
    """혈압 패턴(130/85)을 SBP·DBP로 매핑. 매핑 성공 시 True.

    조건: "혈압"·"BP" 키워드 또는 "mmHg" 단위 포함 + 슬래시 패턴.
    판정 라인(예: "수축기 120-139 또는 이완기 80-89")은 제외.
    """
    if _is_ruling_line(text):
        return False
    bp_match = _BP_PATTERN.search(text)
    if not bp_match:
        return False
    upper = text.upper()
    if "혈압" not in text and "BP" not in upper and "MMHG" not in upper:
        return False
    sbp, dbp = int(bp_match.group(1)), int(bp_match.group(2))
    if "systolic_bp" not in mapped:
        mapped["systolic_bp"] = {"value": sbp, "confidence": conf, "source_text": text}
    if "diastolic_bp" not in mapped:
        mapped["diastolic_bp"] = {"value": dbp, "confidence": conf, "source_text": text}
    return True


def _try_map_height_weight_pair(text: str, conf: float, mapped: dict[str, dict]) -> bool:
    """'키(cm) 및 몸무게(kg) 172 / 68' 처럼 같은 라인에 height·weight 둘 다 있는 경우 동시 매핑."""
    if _is_ruling_line(text):
        return False
    has_h = any(k in text for k in ("키", "신장"))
    has_w = any(k in text for k in ("몸무게", "체중"))
    if not (has_h and has_w):
        return False
    m = _PAIR_PATTERN.search(text)
    if not m:
        return False
    h, w = float(m.group(1)), float(m.group(2))
    if "height" not in mapped:
        mapped["height"] = {"value": h, "confidence": conf, "source_text": text}
    if "weight" not in mapped:
        mapped["weight"] = {"value": w, "confidence": conf, "source_text": text}
    return True


_HW_WINDOW_LINES = 8  # 키→몸무게→172→/→68까지 잡으려면 충분한 윈도우 필요


def _try_map_height_weight_pair_lookahead(lines: list[dict], idx: int, mapped: dict[str, dict]) -> bool:
    """표 형식: '키(cm)'·'및'·'몸무게(kg)'·'172'·'/'·'68' 처럼 토큰별로 잘게 쪼개진 라인을 합쳐서 페어 매핑.

    Clova가 lineBreak를 토큰마다 발화시키는 경우 라인 그룹화가 무력화되므로,
    "키"·"신장" 키워드 라인 발견 시 다음 _HW_WINDOW_LINES만큼 슬라이딩 윈도우로 합쳐
    "몸무게/체중" + 슬래시 페어가 모두 있는지 검사.
    """
    text = lines[idx]["text"]
    if _is_ruling_line(text):
        return False
    if not any(k in text for k in ("키", "신장")):
        return False
    if "height" in mapped and "weight" in mapped:
        return False
    combined_text = text
    combined_conf = lines[idx]["confidence"]
    for j in range(idx + 1, min(idx + 1 + _HW_WINDOW_LINES, len(lines))):
        nt = lines[j]["text"]
        if _is_ruling_line(nt):
            continue
        combined_text += " " + nt
        combined_conf = min(combined_conf, lines[j]["confidence"])
        has_w = any(k in combined_text for k in ("몸무게", "체중"))
        m = _PAIR_PATTERN.search(combined_text)
        if has_w and m:
            h, w = float(m.group(1)), float(m.group(2))
            if "height" not in mapped:
                mapped["height"] = {"value": h, "confidence": combined_conf, "source_text": combined_text}
            if "weight" not in mapped:
                mapped["weight"] = {"value": w, "confidence": combined_conf, "source_text": combined_text}
            return True
    return False


# 정상 범위·판정 표현 — 이런 단어가 들어간 라인은 "값" 아님
_RANGE_WORDS = ("미만", "이상", "이하", "초과", "~", "정상", "주의", "질환", "의심", "참고", "범위", "양호")


def _is_value_line(text: str) -> bool:
    """검진 값(숫자) 라인 판단. 정상 범위·판정·혈압 패턴 제외."""
    if not _NUMBER_PATTERN.search(text):
        return False
    if any(w in text for w in _RANGE_WORDS):
        return False
    if "-" in text or "/" in text:  # 범위·혈압은 별도 처리
        return False
    return True


# 검진 라벨에 자주 붙는 단위·표현 — 이게 있으면 ruling 단어가 섞여 있어도 진짜 라벨 라인
_LABEL_UNIT_HINTS = ("mg/dL", "g/dL", "mmHg", "kg/m", "(cm)", "(kg)", "(mL/min")


def _is_ruling_line(text: str) -> bool:
    """판정·체크박스·정상범위 설명 라인 판단.

    표 행단위 그룹화 후엔 한 줄에 라벨+값+판정이 함께 올 수 있어,
    단위 키워드가 있으면 진짜 라벨 라인으로 인정.
    """
    if not any(w in text for w in _RULING_WORDS):
        return False
    if any(u in text for u in _LABEL_UNIT_HINTS):
        return False
    return True


def _find_matching_field(text: str) -> str | None:
    """라인 텍스트에서 매칭되는 검진 필드명 반환. 우선순위 첫 매치.

    판정·체크박스 라인(□ 정상·의심 등)은 진짜 라벨 가로채기 방지를 위해 제외.
    total_cholesterol는 같은 라인에 "고밀도"·"저밀도"가 있으면 매칭 안 함 —
    HDL/LDL 행이 total로 잘못 매핑되는 경로 차단.
    """
    if _is_ruling_line(text):
        return None
    upper = text.upper()
    has_hdl_ldl_kw = "고밀도" in text or "저밀도" in text
    for field, keywords in _FIELD_KEYWORDS:
        if any(kw in text or kw.upper() in upper for kw in keywords):
            if field == "total_cholesterol" and has_hdl_ldl_kw:
                continue
            return field
    return None


def _try_map_keyword(text: str, conf: float, mapped: dict[str, dict]) -> str | None:
    """같은 라인에 키워드+숫자가 모두 있을 때 매핑. 키워드만 있으면 그 필드명 반환 (다음 라인 검색용)."""
    field = _find_matching_field(text)
    if field is None or field in mapped:
        return None
    num_match = _NUMBER_PATTERN.search(text)
    if num_match:
        mapped[field] = {
            "value": float(num_match.group()),
            "confidence": conf,
            "source_text": text,
        }
        return None
    # 키워드는 있지만 숫자 없음 → 다음 라인 검색이 필요
    return field


_LOOKAHEAD_LINES = 3  # 키워드 라인 다음 N개 라인까지 값 검색 (표 형식 결과지 대응)


def _try_map_with_lookahead(lines: list[dict], idx: int, mapped: dict[str, dict]) -> None:
    """현재 라인의 키워드 + 이어지는 라인의 값으로 매핑.

    한국 검진 결과지는 보통 "공복혈당(mg/dL)\\n92\\n100미만\\n정상" 처럼
    라벨/값/범위/판정이 별도 라인이라 같은 라인 매칭만으론 잡지 못함.
    이 함수는 다음 _LOOKAHEAD_LINES 안의 첫 "값 라인"을 찾아 매핑.
    혈압 키워드 라인은 슬래시 패턴(118/76)을 인접 라인에서 별도로 찾아 SBP·DBP 동시 매핑.
    """
    line = lines[idx]
    text = line["text"]
    conf = line["confidence"]
    # 1) 같은 라인 매칭 (키워드+숫자) — 성공하면 끝
    pending_field = _try_map_keyword(text, conf, mapped)
    if pending_field is None:
        return  # 같은 라인 매칭 성공 또는 키워드 자체 없음
    is_bp = pending_field in ("systolic_bp", "diastolic_bp")
    # 2) 같은 라인엔 키워드만 있었음 → 다음 라인들에서 첫 "값 라인" 찾기
    for j in range(idx + 1, min(idx + 1 + _LOOKAHEAD_LINES, len(lines))):
        next_line = lines[j]
        next_text = next_line["text"]
        next_conf = min(conf, next_line["confidence"])
        # 혈압 라인이면 슬래시 패턴(118/76)을 직접 잡아 SBP·DBP 동시 매핑
        if is_bp and not _is_ruling_line(next_text):
            bp_m = _BP_PATTERN.search(next_text)
            if bp_m:
                sbp, dbp = int(bp_m.group(1)), int(bp_m.group(2))
                src = f"{text} → {next_text}"
                if "systolic_bp" not in mapped:
                    mapped["systolic_bp"] = {"value": sbp, "confidence": next_conf, "source_text": src}
                if "diastolic_bp" not in mapped:
                    mapped["diastolic_bp"] = {"value": dbp, "confidence": next_conf, "source_text": src}
                return
        # 다른 키워드 라인을 만나면 중단 (양식 셀이 바뀜)
        if _find_matching_field(next_text) is not None:
            break
        if _is_value_line(next_text):
            num_match = _NUMBER_PATTERN.search(next_text)
            if num_match:
                mapped[pending_field] = {
                    "value": _to_float(num_match.group()),
                    "confidence": next_conf,
                    "source_text": f"{text} → {next_text}",
                }
                return


def _flatten_fields(page_raws: list[list[dict]]) -> tuple[list[dict], int]:
    """페이지별 raw fields를 평탄화해 (text/confidence 리스트, 저신뢰도 카운트) 반환."""
    fields: list[dict] = []
    low_count = 0
    for page_raw in page_raws:
        for f in page_raw:
            text = (f.get("inferText") or "").strip()
            if not text:
                continue
            conf = float(f.get("inferConfidence") or 0.0)
            if conf < _LOW_CONFIDENCE_THRESHOLD:
                low_count += 1
            fields.append({"text": text, "confidence": round(conf, 3)})
    return fields, low_count


def _map_lines_to_health_fields(lines: list[dict]) -> dict[str, dict]:
    """라인 단위 텍스트에서 검진 수치 자동 매핑.

    반환: {"fasting_glucose": {"value": 118.0, "confidence": 0.96, "source_text": "공복혈당 118 mg/dL"}, ...}
    매핑되지 않은 필드는 dict에 키 없음.
    """
    mapped: dict[str, dict] = {}
    for idx, line in enumerate(lines):
        text = line["text"]
        conf = line["confidence"]
        # 키+몸무게 같은 라인 ("키(cm) 및 몸무게(kg) 172 / 68") 우선
        if _try_map_height_weight_pair(text, conf, mapped):
            continue
        # 표 형식: 키+몸무게 라벨 라인 + 다음 라인 페어
        if _try_map_height_weight_pair_lookahead(lines, idx, mapped):
            continue
        # 혈압 "130/85" 우선 처리
        if _try_map_blood_pressure(text, conf, mapped):
            continue
        # 같은 라인 또는 인접 라인에서 매핑
        _try_map_with_lookahead(lines, idx, mapped)
    return mapped


_PURE_NUMBER_RE = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$")
_SKIP_TOKEN_WORDS = (
    "이상",
    "미만",
    "이하",
    "초과",
    "정상",
    "의심",
    "주의",
    "□",
    "■",
    "유질환자",
    "전단계",
    "낮은",
    "고위험",
    "이상자",
    "장애",
)


def _classify_tokens(items: list[dict]) -> tuple[list[tuple[str, dict]], list[dict], list[dict]]:
    """토큰을 (라벨 후보, 단독 숫자, 페어 패턴)으로 분류."""
    labels: list[tuple[str, dict]] = []
    numbers: list[dict] = []
    pairs: list[dict] = []
    for it in items:
        text = it["text"]
        pm = _PAIR_PATTERN.fullmatch(text)
        if pm:
            pairs.append({**it, "v1": float(pm.group(1)), "v2": float(pm.group(2))})
            continue
        if _PURE_NUMBER_RE.fullmatch(text):
            numbers.append({**it, "value": _to_float(text)})
            continue
        if any(w in text for w in _SKIP_TOKEN_WORDS):
            continue
        field = _find_matching_field(text)
        if field is not None:
            labels.append((field, it))
    return labels, numbers, pairs


def _same_row(a: dict, b: dict, factor: float = 0.6) -> bool:
    """두 토큰이 같은 표 행인지 — y_mid 차이가 평균 토큰 높이의 factor 이내."""
    ref = max(a["y_bot"] - a["y_top"], b["y_bot"] - b["y_top"])
    return ref > 0 and abs(a["y_mid"] - b["y_mid"]) <= ref * factor


def _map_labels_with_numbers(labels: list[tuple[str, dict]], numbers: list[dict], mapped: dict[str, dict]) -> None:
    """일반 라벨 → 같은 행 우측 가장 가까운 단독 숫자 토큰 매핑."""
    for field, lt in labels:
        if field in mapped:
            continue
        candidates = [nt for nt in numbers if nt["x"] > lt["x"] and _same_row(lt, nt)]
        if not candidates:
            continue
        best = min(candidates, key=lambda nt: nt["x"] - lt["x"])
        mapped[field] = {
            "value": best["value"],
            "confidence": round(min(lt["conf"], best["conf"]), 3),
            "source_text": f"{lt['text']} → {best['text']}",
        }


def _map_height_weight_pair_token(labels: list[tuple[str, dict]], pairs: list[dict], mapped: dict[str, dict]) -> None:
    """키 라벨 + 같은 행 페어 토큰("172 / 68")으로 height·weight 동시 매핑."""
    if "height" in mapped and "weight" in mapped:
        return
    height_lt = next((lt for f, lt in labels if f == "height"), None)
    if height_lt is None:
        return
    for pt in pairs:
        if not _same_row(height_lt, pt):
            continue
        src = f"{height_lt['text']} → {pt['text']}"
        if "height" not in mapped:
            mapped["height"] = {"value": pt["v1"], "confidence": round(pt["conf"], 3), "source_text": src}
        if "weight" not in mapped:
            mapped["weight"] = {"value": pt["v2"], "confidence": round(pt["conf"], 3), "source_text": src}
        return


def _map_tokens_by_position(page_raws: list[list[dict]], mapped: dict[str, dict]) -> None:
    """토큰 좌표 기반 페어 매칭 — 라벨의 같은 행 + 우측 가장 가까운 숫자 토큰 매핑.

    라인 단위 매핑이 못 잡은 필드 보강. boundingPoly 좌표가 없으면 noop.
    """
    for page_raw in page_raws:
        items = _extract_token_items(page_raw)
        if not items:
            continue
        labels, numbers, pairs = _classify_tokens(items)
        _map_labels_with_numbers(labels, numbers, mapped)
        _map_height_weight_pair_token(labels, pairs, mapped)


_NEXT_ROW_LABELS = ("중성지방", "저밀도", "트리글리세라이드")  # HDL 행 다음에 오는 라벨 — 셀 경계


def _fallback_hdl_strict_row(page_raws: list[list[dict]], mapped: dict[str, dict]) -> None:
    """PDF 검진 결과지 '고밀도 콜레스테롤(mg/dL)' 행 전용 룰 (옵션 D).

    두 줄 셀(고밀도 / 콜레스테롤(mg/dL))로 y범위가 커서 인접 행 숫자를 흡수하는
    문제를 차단:
    - '고밀도' 토큰 발견 (같은 행에 판정 단어 없음 = 진짜 라벨 라인)
    - 그 토큰 아래의 첫 '중성지방'·'저밀도' 라벨 y_top까지를 셀 y_bot
    - 셀 y범위 안의 우측 첫 단독 숫자 = HDL 값
    - 60이상 같은 합성 토큰은 _PURE_NUMBER_RE에 안 잡혀 자동 제외
    """
    if "hdl_cholesterol" in mapped:
        return
    for page_raw in page_raws:
        items = _extract_token_items(page_raw)
        if not items:
            continue
        if _try_hdl_strict_row(items, mapped):
            return


def _try_hdl_strict_row(items: list[dict], mapped: dict[str, dict]) -> bool:
    """한 페이지 안에서 옵션 D 룰 시도. 성공 시 True.

    kw_tokens: "고밀도" 포함 토큰 (단독 또는 결합형 "고밀도 콜레스테롤(mg/dL)" 모두 인정).
    단 토큰 텍스트 자체에 판정 단어("낮은"·"의심" 등)가 있으면 진짜 라벨 아님 → 제외.
    같은 행 다른 토큰 검사는 안 함 — HDL 행 우측 판정 컬럼에 판정 단어가 정상 존재.
    """
    bad_words = ("낮은", "의심", "고위험", "전단계", "이상자", "유질환자")
    kw_tokens = [it for it in items if "고밀도" in it["text"] and not any(b in it["text"] for b in bad_words)]
    if not kw_tokens:
        return False
    if not any("콜레스테롤" in it["text"] for it in items):
        return False
    nums = [{**it, "value": _to_float(it["text"])} for it in items if _PURE_NUMBER_RE.fullmatch(it["text"])]
    for kt in kw_tokens:
        # 다음 행 라벨(중성지방·저밀도) y_top — 셀 아래 경계
        next_y_tops = [
            it["y_top"] for it in items if any(k in it["text"] for k in _NEXT_ROW_LABELS) and it["y_top"] > kt["y_bot"]
        ]
        if not next_y_tops:
            continue
        cell_y_bot = min(next_y_tops)
        # 셀 y범위 안 + 라벨 우측 단독 숫자
        candidates = [n for n in nums if n["x"] > kt["x"] and kt["y_top"] <= n["y_mid"] < cell_y_bot]
        if not candidates:
            continue
        best = min(candidates, key=lambda n: n["x"])
        mapped["hdl_cholesterol"] = {
            "value": best["value"],
            "confidence": round(min(kt["conf"], best["conf"]), 3),
            "source_text": f"{kt['text']} → {best['text']}",
        }
        return True
    return False


def _fallback_split_cholesterol(page_raws: list[list[dict]], mapped: dict[str, dict]) -> None:
    """단독 '고밀도' 토큰이 라벨 매칭에 실패한 경우 HDL 보강.

    Clova가 "고밀도 콜레스테롤(mg/dL)" 셀을 두 토큰으로 쪼개거나, 라인 그룹화가 묶지 못해
    토큰 매핑이 잘못된 행 숫자를 매핑한 케이스를 정확히 처리. LDL은 시스템에서 사용하지
    않으므로 처리 안 함.

    안전 장치:
    - hdl_cholesterol이 이미 mapped면 절대 발동 안 함
    - "콜레스테롤" 토큰에 단위(mg/dL) 키워드 필수 — 판정 라인의 "콜레스테롤"은 단위 없어 제외
    - "낮은"·"의심" 토큰이 같은 행에 있으면 가로채기 위험으로 발동 중단
    - 숫자 후보는 (kt, ct) 페어의 y범위 안에 y_mid가 들어오는 토큰만 — 인접 행 숫자 차단
    """
    field = "hdl_cholesterol"
    if field in mapped:
        return
    for page_raw in page_raws:
        items = _extract_token_items(page_raw)
        if not items:
            continue
        if _try_fallback_one_page(items, field, "고밀도", mapped):
            return


def _try_fallback_one_page(items: list[dict], field: str, kw: str, mapped: dict[str, dict]) -> bool:
    """한 페이지 안에서 단독 키워드 토큰 fallback 시도. 매핑 성공 시 True."""
    kw_tokens = [it for it in items if it["text"].strip() == kw]
    if not kw_tokens:
        return False
    cho_tokens = [it for it in items if "콜레스테롤" in it["text"] and any(u in it["text"] for u in _LABEL_UNIT_HINTS)]
    if not cho_tokens:
        return False
    nums = [{**it, "value": _to_float(it["text"])} for it in items if _PURE_NUMBER_RE.fullmatch(it["text"])]
    bad_words = ("낮은", "의심", "고위험", "전단계", "이상자", "유질환자")
    for kt in kw_tokens:
        if any(any(w in it["text"] for w in bad_words) for it in items if it is not kt and _same_row(kt, it)):
            continue
        # 가장 가까운 ct (라벨 페어로 인정할 토큰 높이 2.5배 이내)
        kt_h = kt["y_bot"] - kt["y_top"]
        ct = min(
            (c for c in cho_tokens if abs(c["y_mid"] - kt["y_mid"]) <= max(kt_h, c["y_bot"] - c["y_top"]) * 2.5),
            key=lambda c: abs(c["y_mid"] - kt["y_mid"]) + abs(c["x"] - kt["x"]) * 0.3,
            default=None,
        )
        if ct is None:
            continue
        # 라벨 페어 y범위 안의 숫자만 후보 (인접 행 숫자 차단)
        y_top = min(kt["y_top"], ct["y_top"])
        y_bot = max(kt["y_bot"], ct["y_bot"])
        anchor_x = max(kt["x"], ct["x"])
        candidates = [n for n in nums if n["x"] > anchor_x and y_top <= n["y_mid"] <= y_bot]
        # 후보가 정확히 1개일 때만 매핑 — 여러 개면 모호하므로 비워둠 (잘못된 매핑보다 빈칸이 안전)
        if len(candidates) != 1:
            continue
        best = candidates[0]
        mapped[field] = {
            "value": best["value"],
            "confidence": round(min(kt["conf"], ct["conf"], best["conf"]), 3),
            "source_text": f"{kt['text']} {ct['text']} → {best['text']}",
        }
        return True
    return False


def _split_pdf_pages(pdf_bytes: bytes) -> list[bytes]:
    """다중 페이지 PDF → 페이지별 단일 페이지 PDF bytes 리스트.

    Clova General OCR이 다중 페이지 PDF에서 400 거절 사례가 있어,
    각 페이지를 단일 페이지 PDF로 분리해 페이지마다 호출한다.
    페이지 1개거나 손상이면 원본 그대로 반환 (이후 단계가 거절 처리).
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if len(reader.pages) <= 1:
            return [pdf_bytes]
        pages: list[bytes] = []
        for page in reader.pages:
            writer = PdfWriter()
            writer.add_page(page)
            buf = io.BytesIO()
            writer.write(buf)
            pages.append(buf.getvalue())
        return pages
    except Exception as exc:  # noqa: BLE001 — 손상된 PDF 등 모든 예외를 단일 페이지 처리로 fallback
        logger.warning("PDF 페이지 분할 실패 — 단일 페이지로 처리: %s", type(exc).__name__)
        return [pdf_bytes]


async def _call_clova_for_page(
    *,
    invoke_url: str,
    secret_key: str,
    image_format: str,
    page_bytes: bytes,
    content_type: str,
    page_idx: int,
) -> list[dict]:
    """단일 페이지(또는 이미지) Clova 호출 + 응답 파싱."""
    message = json.dumps(
        {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [{"format": image_format, "name": f"checkup_p{page_idx}"}],
        }
    )
    resp = await _post_to_clova(
        invoke_url=invoke_url,
        secret_key=secret_key,
        message=message,
        file_bytes=page_bytes,
        content_type=content_type,
        filename=f"checkup.{image_format}",
    )
    return _parse_clova_response(resp)


def _validate_magic_bytes(file_bytes: bytes, image_format: str) -> None:
    """파일 매직 바이트로 실제 형식 검증. content_type만 보면 docx→.pdf 같은 위장 못 잡음."""
    if image_format == "pdf" and not file_bytes.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF 파일이 손상됐거나 실제 형식이 PDF가 아닙니다. 결과지를 다시 저장해 시도해주세요.",
        )
    if image_format in ("jpg",) and not file_bytes.startswith(_JPEG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JPG 파일이 손상됐거나 실제 형식이 JPG가 아닙니다.",
        )
    if image_format == "png" and not file_bytes.startswith(_PNG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PNG 파일이 손상됐거나 실제 형식이 PNG가 아닙니다.",
        )


async def _post_to_clova(
    *, invoke_url: str, secret_key: str, message: str, file_bytes: bytes, content_type: str, filename: str
) -> httpx.Response:
    """Clova API HTTP 호출만 담당. 타임아웃·네트워크 오류는 한국어 HTTPException으로 변환."""
    try:
        async with httpx.AsyncClient(timeout=_CLOVA_TIMEOUT_SEC) as client:
            return await client.post(
                invoke_url,
                headers={"X-OCR-SECRET": secret_key},
                files={
                    "message": (None, message, "application/json"),
                    "file": (filename, file_bytes, content_type),
                },
            )
    except httpx.TimeoutException as exc:
        logger.warning("Clova OCR 타임아웃")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="OCR 처리가 지연됩니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Clova OCR 네트워크 오류: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR 서비스에 일시적으로 접근할 수 없습니다. 잠시 후 다시 시도해주세요.",
        ) from exc


def _parse_clova_response(resp: httpx.Response) -> list[dict]:
    """Clova 응답 검증·파싱. 비정상이면 한국어 HTTPException."""
    if resp.status_code in (401, 403):
        logger.error("Clova OCR 인증 실패 status=%s", resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR 서비스 인증 오류입니다. 관리자에게 문의하세요.",
        )
    if resp.status_code != 200:
        # 응답 본문 일부도 로그에 — Clova 오류 메시지로 원인 추적 (PII 없음, 운영 환경엔 길이 축소 검토)
        logger.error("Clova OCR 오류 status=%s body=%s", resp.status_code, resp.text[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OCR 서비스가 응답 오류를 반환했습니다.",
        )

    try:
        image = resp.json()["images"][0]
        infer_result = image.get("inferResult")
        fields_raw = image.get("fields", [])
    except (KeyError, IndexError, ValueError) as exc:
        logger.error("Clova OCR 응답 파싱 실패")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OCR 응답을 해석할 수 없습니다.",
        ) from exc

    if infer_result != "SUCCESS":
        logger.warning("Clova OCR 추출 실패 inferResult=%s", infer_result)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="이미지에서 텍스트를 추출하지 못했습니다. 더 선명한 이미지로 다시 시도해주세요.",
        )
    return fields_raw


# 검진 항목별 생리적 유효 범위 — 범위 밖 매핑은 오인식(정상범위 컬럼·소수점 오류·콤마 잔류 등)으로
# 보고 제거한다. 자동입력에 비현실 값이 들어가는 것보다 빈칸으로 두고 사용자가 직접 입력하는 편이 안전.
_VALID_RANGES: dict[str, tuple[float, float]] = {
    "systolic_bp": (60.0, 260.0),
    "diastolic_bp": (30.0, 160.0),
    "fasting_glucose": (20.0, 600.0),
    "creatinine": (0.2, 20.0),
    "total_cholesterol": (50.0, 500.0),
    "hdl_cholesterol": (10.0, 150.0),
    "triglycerides": (20.0, 5000.0),
    "height": (100.0, 220.0),
    "weight": (20.0, 250.0),
    "waist_circumference": (40.0, 200.0),
}


def _drop_out_of_range(mapped: dict[str, dict]) -> list[str]:
    """생리적 범위를 벗어난 매핑값을 제거(오인식 차단). 제거한 필드명 리스트 반환."""
    dropped: list[str] = []
    for field, (lo, hi) in _VALID_RANGES.items():
        m = mapped.get(field)
        if m is None:
            continue
        value = m.get("value")
        if value is None or not (lo <= value <= hi):
            mapped.pop(field, None)
            if value is not None:
                dropped.append(f"{field}={value}")
    return dropped


async def extract_text(*, file_bytes: bytes, content_type: str, filename: str) -> dict:
    """Clova OCR API 호출 → 텍스트·신뢰도 추출."""
    invoke_url = os.getenv("CLOVA_OCR_INVOKE_URL")
    secret_key = os.getenv("CLOVA_OCR_SECRET_KEY")
    if not invoke_url or not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR 기능이 설정되지 않았습니다. 관리자에게 문의하세요.",
        )

    image_format = _MIME_TO_FORMAT.get(content_type or "")
    if image_format is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원하지 않는 파일 형식입니다.",
        )

    # 파일 매직 바이트 검증 — content_type만 신뢰하지 않음 (확장자만 .pdf로 바꾼 docx 등 차단)
    _validate_magic_bytes(file_bytes, image_format)

    # 다중 페이지 PDF는 페이지별로 분리해 Clova에 순차 호출 (General OCR이 다중 페이지에서 400 거절 사례 있음)
    pages = _split_pdf_pages(file_bytes) if image_format == "pdf" else [file_bytes]
    page_count = len(pages)

    page_raws: list[list[dict]] = []
    page_errors: list[str] = []
    for page_idx, page_bytes in enumerate(pages, 1):
        try:
            page_raw = await _call_clova_for_page(
                invoke_url=invoke_url,
                secret_key=secret_key,
                image_format=image_format,
                page_bytes=page_bytes,
                content_type=content_type,
                page_idx=page_idx,
            )
            page_raws.append(page_raw)
        except HTTPException as exc:
            # 부분 실패 허용 — 일부 페이지 실패해도 성공한 페이지의 fields는 보존
            logger.warning("Clova OCR 페이지 %d 실패: %s", page_idx, exc.detail)
            page_errors.append(f"페이지 {page_idx}: {exc.detail}")

    if not page_raws and page_errors:
        # 모든 페이지 실패
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"모든 페이지에서 텍스트 추출에 실패했습니다. ({page_errors[0]})",
        )

    fields, low_count = _flatten_fields(page_raws)

    # 라인 그루핑은 페이지별로 따로 (페이지 좌표 origin 겹침으로 다른 페이지 토큰이
    # 같은 줄로 묶이는 문제 방지) → 결과 라인 리스트만 concat
    lines: list[dict] = []
    for page_raw in page_raws:
        lines.extend(_group_into_lines(page_raw))
    mapped = _map_lines_to_health_fields(lines)
    # 라인 매핑이 못 잡은 필드는 토큰 좌표 기반 페어 매칭으로 보강
    _map_tokens_by_position(page_raws, mapped)
    # PDF 검진 결과지 '고밀도 콜레스테롤(mg/dL)' 두 줄 셀 전용 룰 (옵션 D) — 가장 정교
    _fallback_hdl_strict_row(page_raws, mapped)
    # 분리된 "고밀도" + "콜레스테롤(mg/dL)" 토큰 일반 fallback (옵션 D가 못 잡았을 때만)
    _fallback_split_cholesterol(page_raws, mapped)
    # 생리적 범위 벗어난 매핑값 제거 (콤마 잔류·정상범위 컬럼·소수점 오류 등 오인식 차단)
    out_of_range = _drop_out_of_range(mapped)
    if out_of_range:
        logger.info("OCR 범위초과 매핑 제거: %s", out_of_range)

    logger.info(
        "Clova OCR 추출 성공 pages=%d fields=%d lines=%d mapped=%d low_conf=%d errors=%d mapped_keys=%s",
        page_count,
        len(fields),
        len(lines),
        len(mapped),
        low_count,
        len(page_errors),
        ",".join(sorted(mapped.keys())) or "(none)",
    )
    return {
        "engine": "clova",
        "filename": filename or "checkup",
        "fields": fields,
        "lines": lines,
        "mapped": mapped,
        "low_confidence_count": low_count,
        "page_count": page_count,
        "page_errors": page_errors,
    }
