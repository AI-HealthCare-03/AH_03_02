"""Clova OCR 서비스 — 검진 결과지 이미지 → 텍스트·신뢰도 추출.

NAVER Clova OCR General API를 multipart/form-data로 호출하고 응답 JSON에서
fields[].inferText·inferConfidence만 추려 깔끔한 dict로 반환한다.

외부 API 오류·키 미설정·타임아웃·인증 실패는 모두 한국어 detail의 HTTPException으로 변환.
원본 상태 코드·응답 본문은 로그에만 남기고 사용자 응답에는 노출하지 않는다.
"""

import io
import json
import os
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

# 파일 매직 바이트 — content_type만 신뢰하지 않고 실제 파일 시그니처 검증
# (사용자가 docx를 .pdf로 잘못 저장한 케이스 등을 친절한 한국어 에러로 변환)
_PDF_MAGIC = b"%PDF-"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


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

    logger.info(
        "Clova OCR 추출 성공 pages=%d fields=%d low_conf=%d errors=%d",
        page_count,
        len(fields),
        low_count,
        len(page_errors),
    )
    return {
        "engine": "clova",
        "filename": filename or "checkup",
        "fields": fields,
        "low_confidence_count": low_count,
        "page_count": page_count,
        "page_errors": page_errors,
    }
