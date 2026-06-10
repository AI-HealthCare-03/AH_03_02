"""Clova OCR 서비스 — 검진 결과지 이미지 → 텍스트·신뢰도 추출.

NAVER Clova OCR General API를 multipart/form-data로 호출하고 응답 JSON에서
fields[].inferText·inferConfidence만 추려 깔끔한 dict로 반환한다.

외부 API 오류·키 미설정·타임아웃·인증 실패는 모두 한국어 detail의 HTTPException으로 변환.
원본 상태 코드·응답 본문은 로그에만 남기고 사용자 응답에는 노출하지 않는다.
"""

import json
import os
import time
import uuid

import httpx
from fastapi import HTTPException, status

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
        logger.error("Clova OCR 오류 status=%s", resp.status_code)
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

    message = json.dumps(
        {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [{"format": image_format, "name": "checkup"}],
        }
    )

    resp = await _post_to_clova(
        invoke_url=invoke_url,
        secret_key=secret_key,
        message=message,
        file_bytes=file_bytes,
        content_type=content_type,
        filename=filename or "checkup",
    )
    fields_raw = _parse_clova_response(resp)

    fields: list[dict] = []
    low_count = 0
    for f in fields_raw:
        text = (f.get("inferText") or "").strip()
        if not text:
            continue
        conf = float(f.get("inferConfidence") or 0.0)
        if conf < _LOW_CONFIDENCE_THRESHOLD:
            low_count += 1
        fields.append({"text": text, "confidence": round(conf, 3)})

    logger.info("Clova OCR 추출 성공 fields=%d low_conf=%d", len(fields), low_count)
    return {
        "engine": "clova",
        "filename": filename or "checkup",
        "fields": fields,
        "low_confidence_count": low_count,
    }
