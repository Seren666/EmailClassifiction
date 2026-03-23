from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pipeline import DEFAULT_MAX_PAGES, PipelineError, ZERO_STATS, run_pipeline


LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

HTTP_STATUS_BY_CODE = {
    "OK": 200,
    "INVALID_REQUEST": 400,
    "PATH_NOT_FOUND": 404,
    "PARSE_FAILED": 422,
    "NO_EMAIL_FOUND": 422,
    "INTERNAL_ERROR": 500,
}

app = FastAPI(title="Author Email Extractor API", version="1.0.0")


@app.post("/extract-author-emails")
async def extract_author_emails(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        envelope, status_code = build_response_from_payload(None)
        return JSONResponse(content=envelope, status_code=status_code)

    envelope, status_code = build_response_from_payload(payload)
    return JSONResponse(content=envelope, status_code=status_code)


def build_response_from_payload(
    payload: Any,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    debug: bool = False,
) -> tuple[dict[str, Any], int]:
    if not isinstance(payload, dict):
        return _error_envelope("INVALID_REQUEST", "pdf_path is required"), HTTP_STATUS_BY_CODE["INVALID_REQUEST"]

    raw_pdf_path = payload.get("pdf_path")
    if not isinstance(raw_pdf_path, str) or not raw_pdf_path.strip():
        return _error_envelope("INVALID_REQUEST", "pdf_path is required"), HTTP_STATUS_BY_CODE["INVALID_REQUEST"]

    pdf_path = raw_pdf_path.strip()
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return _error_envelope("PATH_NOT_FOUND", "pdf_path does not exist"), HTTP_STATUS_BY_CODE["PATH_NOT_FOUND"]

    try:
        result = run_pipeline(path, max_pages=max_pages, debug=debug)
    except PipelineError as exc:
        LOGGER.warning("pipeline error code=%s pdf=%s detail=%s", exc.code, path, exc.detail)
        return _error_envelope(exc.code, exc.message, stats=exc.stats), HTTP_STATUS_BY_CODE[exc.code]
    except Exception as exc:
        LOGGER.exception("unexpected internal error for pdf=%s", path)
        return _error_envelope("INTERNAL_ERROR", "internal error"), HTTP_STATUS_BY_CODE["INTERNAL_ERROR"]

    structured_email_string = json.dumps(result.structured_output, ensure_ascii=False)
    envelope = {
        "structured_email_string": structured_email_string,
        "stats": dict(result.stats),
        "code": "OK",
        "message": "success",
    }
    return envelope, HTTP_STATUS_BY_CODE["OK"]


def _error_envelope(
    code: str,
    message: str,
    *,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "structured_email_string": "",
        "stats": dict(stats or ZERO_STATS),
        "code": code,
        "message": message,
    }


__all__ = ["app", "build_response_from_payload"]
