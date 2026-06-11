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

# ManualInputPage form 필드 → 키워드 매핑. HDL이 "콜레스테롤" 키워드보다 먼저(우선순위).
_FIELD_KEYWORDS: list[tuple[str, list[str]]] = [
    ("fasting_glucose", ["공복혈당", "혈당", "glucose"]),
    ("creatinine", ["크레아티닌", "creatinine"]),
    ("hdl_cholesterol", ["HDL", "고밀도"]),
    ("ldl_cholesterol", ["LDL", "저밀도"]),
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
# 숫자 (소수 허용)
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")

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


def _group_into_lines(fields_raw: list[dict]) -> list[dict]:
    """Clova fields[].lineBreak로 같은 줄 토큰을 합쳐 라인 단위로 반환.

    반환: [{"text": "공복혈당 118 mg/dL", "confidence": 0.96}, ...]
    같은 라인 토큰들의 신뢰도는 최솟값 사용 (보수적).
    """
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


def _is_ruling_line(text: str) -> bool:
    """판정·체크박스·정상범위 설명 라인 판단. 진짜 라벨이 아니므로 키워드 매칭 제외."""
    return any(w in text for w in _RULING_WORDS)


def _find_matching_field(text: str) -> str | None:
    """라인 텍스트에서 매칭되는 검진 필드명 반환. 우선순위 첫 매치.

    판정·체크박스 라인(□ 정상·의심 등)은 진짜 라벨 가로채기 방지를 위해 제외.
    """
    if _is_ruling_line(text):
        return None
    upper = text.upper()
    for field, keywords in _FIELD_KEYWORDS:
        if any(kw in text or kw.upper() in upper for kw in keywords):
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
                    "value": float(num_match.group()),
                    "confidence": next_conf,
                    "source_text": f"{text} → {next_text}",
                }
                return


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

    all_raw: list[dict] = []
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
            all_raw.extend(page_raw)
        except HTTPException as exc:
            # 부분 실패 허용 — 일부 페이지 실패해도 성공한 페이지의 fields는 보존
            logger.warning("Clova OCR 페이지 %d 실패: %s", page_idx, exc.detail)
            page_errors.append(f"페이지 {page_idx}: {exc.detail}")

    if not all_raw and page_errors:
        # 모든 페이지 실패
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"모든 페이지에서 텍스트 추출에 실패했습니다. ({page_errors[0]})",
        )

    fields: list[dict] = []
    low_count = 0
    for f in all_raw:
        text = (f.get("inferText") or "").strip()
        if not text:
            continue
        conf = float(f.get("inferConfidence") or 0.0)
        if conf < _LOW_CONFIDENCE_THRESHOLD:
            low_count += 1
        fields.append({"text": text, "confidence": round(conf, 3)})

    # 라인 그루핑 + 자동 필드 매핑 — 사용자가 검진 입력 페이지에서 prefill로 받음
    lines = _group_into_lines(all_raw)
    mapped = _map_lines_to_health_fields(lines)

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
