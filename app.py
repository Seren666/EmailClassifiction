from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

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


class ExtractAuthorEmailsRequest(BaseModel):
    pdf_path: str = Field(
        ...,
        description="Enter a local or mounted PDF path.",
        examples=["C:/path/to/file.pdf"],
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pdf_path": "C:/path/to/file.pdf"
            }
        }
    )


UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Author Email Extractor</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f4;
      --panel: #ffffff;
      --border: #d8ded6;
      --text: #17311f;
      --muted: #5e7164;
      --accent: #2d6a4f;
      --accent-strong: #1f4d39;
      --error: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      background: linear-gradient(180deg, #eef4ee 0%, var(--bg) 100%);
      color: var(--text);
    }
    .wrap {
      max-width: 780px;
      margin: 0 auto;
      padding: 48px 20px 64px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 24px;
      box-shadow: 0 18px 50px rgba(23, 49, 31, 0.08);
    }
    h1 {
      margin: 0 0 10px;
      font-size: 32px;
      line-height: 1.1;
    }
    p {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.6;
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
    }
    input {
      width: 100%;
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: 12px;
      font-size: 15px;
      color: var(--text);
      background: #fbfcfb;
    }
    input:focus {
      outline: 2px solid rgba(45, 106, 79, 0.2);
      border-color: var(--accent);
    }
    button {
      margin-top: 16px;
      padding: 12px 18px;
      border: none;
      border-radius: 12px;
      background: var(--accent);
      color: white;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover { background: var(--accent-strong); }
    button:disabled { opacity: 0.6; cursor: wait; }
    .results {
      margin-top: 24px;
      display: grid;
      gap: 12px;
    }
    .card {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      background: #fcfdfc;
    }
    .key {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value {
      font-size: 18px;
      word-break: break-word;
    }
    .status-ok { color: var(--accent-strong); }
    .status-error { color: var(--error); }
    details {
      margin-top: 12px;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px 14px;
      background: #fbfcfb;
    }
    summary {
      cursor: pointer;
      font-weight: 600;
    }
    pre {
      margin: 12px 0 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
      line-height: 1.5;
      color: var(--text);
    }
    .footer {
      margin-top: 14px;
      font-size: 13px;
      color: var(--muted);
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>Author Email Extractor</h1>
      <p>Submit a PDF path and view the most important fields first. Full JSON stays collapsed unless you need it.</p>
      <label for="pdf-path">PDF Path</label>
      <input id="pdf-path" type="text" placeholder="C:/path/to/file.pdf" autocomplete="off">
      <button id="run-btn" type="button">Execute</button>
      <div class="results" id="results" hidden>
        <div class="card">
          <span class="key">Code</span>
          <div class="value" id="code-value"></div>
        </div>
        <div class="card">
          <span class="key">Message</span>
          <div class="value" id="message-value"></div>
        </div>
        <div class="card">
          <span class="key">First Author</span>
          <div class="value" id="first-author-value">-</div>
        </div>
        <div class="card">
          <span class="key">First Author Email</span>
          <div class="value" id="first-author-email-value">-</div>
        </div>
        <div class="card">
          <span class="key">First Author Region</span>
          <div class="value" id="first-author-region-value">-</div>
        </div>
        <details>
          <summary>Expand full response</summary>
          <pre id="raw-response"></pre>
        </details>
      </div>
      <div class="footer">You can also use <a href="/docs">/docs</a> for Swagger UI or <a href="/openapi.json">/openapi.json</a> for the schema.</div>
    </div>
  </div>
  <script>
    const input = document.getElementById("pdf-path");
    const button = document.getElementById("run-btn");
    const results = document.getElementById("results");
    const codeValue = document.getElementById("code-value");
    const messageValue = document.getElementById("message-value");
    const firstAuthorValue = document.getElementById("first-author-value");
    const firstAuthorEmailValue = document.getElementById("first-author-email-value");
    const firstAuthorRegionValue = document.getElementById("first-author-region-value");
    const rawResponse = document.getElementById("raw-response");

    async function runRequest() {
      const pdfPath = input.value.trim();
      button.disabled = true;
      button.textContent = "Running...";
      try {
        const response = await fetch("/extract-author-emails", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pdf_path: pdfPath })
        });
        const data = await response.json();
        let payload = null;
        if (data.structured_email_string) {
          try {
            payload = JSON.parse(data.structured_email_string);
          } catch (error) {
            payload = null;
          }
        }

        results.hidden = false;
        codeValue.textContent = data.code || "-";
        codeValue.className = "value " + ((data.code === "OK") ? "status-ok" : "status-error");
        messageValue.textContent = data.message || "-";
        firstAuthorValue.textContent = payload?.first_author?.author_norm || "-";
        firstAuthorEmailValue.textContent = payload?.first_author_email || "-";
        firstAuthorRegionValue.textContent = payload?.first_author_region || "-";
        rawResponse.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        results.hidden = false;
        codeValue.textContent = "REQUEST_FAILED";
        codeValue.className = "value status-error";
        messageValue.textContent = error.message;
        firstAuthorValue.textContent = "-";
        firstAuthorEmailValue.textContent = "-";
        firstAuthorRegionValue.textContent = "-";
        rawResponse.textContent = error.stack || String(error);
      } finally {
        button.disabled = false;
        button.textContent = "Execute";
      }
    }

    button.addEventListener("click", runRequest);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        runRequest();
      }
    });
  </script>
</body>
</html>
"""


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Any,
    exc: RequestValidationError,
) -> JSONResponse:
    LOGGER.warning("request validation failed errors=%s", exc.errors())
    envelope = _error_envelope("INVALID_REQUEST", "pdf_path is required")
    return JSONResponse(content=envelope, status_code=HTTP_STATUS_BY_CODE["INVALID_REQUEST"])


@app.get("/", response_class=HTMLResponse, summary="Minimal web UI")
async def minimal_ui() -> HTMLResponse:
    return HTMLResponse(UI_HTML)


@app.post(
    "/extract-author-emails",
    summary="Extract authors, emails, pairs and first-author fields from a PDF",
    description=(
        "Submit a local PDF path. The response envelope stays stable in V1: "
        "`structured_email_string`, `stats`, `code`, `message`."
    ),
)
async def extract_author_emails(request: ExtractAuthorEmailsRequest) -> JSONResponse:
    envelope, status_code = build_response_from_payload(request.model_dump())
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
