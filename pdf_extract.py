from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_PAGES = 2
DEFAULT_READABLE_MIN_CHARS = 80


class PDFExtractError(RuntimeError):
    """Raised when a PDF cannot be opened or no extractor can process it."""


@dataclass
class PageText:
    page_number: int
    text: str
    extractor_used: str
    blocks: list[dict[str, Any]] | None = None
    lines: list[dict[str, Any]] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_readable_text(text: str, min_chars: int = DEFAULT_READABLE_MIN_CHARS) -> bool:
    """Simple, explainable readability rule for downstream smoke checks."""
    normalized = "".join(text.split())
    return len(normalized) >= min_chars


def extract_pages(pdf_path: str | Path, max_pages: int = DEFAULT_MAX_PAGES) -> list[PageText]:
    """
    Extract text from the first pages of a PDF.

    Strategy:
    1. Try PyMuPDF (fitz) first.
    2. For pages that fail or are empty, retry those pages with pdfplumber.
    3. Keep page-level failures isolated so one bad page does not crash the whole file.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF path does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"PDF path is not a file: {path}")
    if max_pages <= 0:
        raise ValueError("max_pages must be greater than 0")

    fitz_pages, fitz_error = _extract_with_fitz(path, max_pages)
    if fitz_pages:
        return _fill_missing_pages_with_pdfplumber(path, max_pages, fitz_pages)

    plumber_pages, plumber_error = _extract_with_pdfplumber(path, max_pages)
    if plumber_pages:
        return plumber_pages

    reasons = [reason for reason in [fitz_error, plumber_error] if reason]
    detail = " | ".join(reasons) if reasons else "unknown extraction failure"
    raise PDFExtractError(f"Failed to extract readable text from {path}: {detail}")


def _extract_with_fitz(path: Path, max_pages: int) -> tuple[list[PageText], str | None]:
    try:
        import fitz
    except ImportError as exc:
        return [], f"PyMuPDF unavailable: {exc}"

    pages: list[PageText] = []
    try:
        with fitz.open(path) as doc:
            page_count = min(max_pages, len(doc))
            for page_index in range(page_count):
                try:
                    page = doc[page_index]
                    text = page.get_text("text") or ""
                    blocks = _fitz_blocks(page)
                    lines = _fitz_lines(page)
                    pages.append(
                        PageText(
                            page_number=page_index + 1,
                            text=text,
                            extractor_used="fitz",
                            blocks=blocks or None,
                            lines=lines or None,
                            error=None if text.strip() else "empty_text_from_fitz",
                        )
                    )
                except Exception as exc:
                    pages.append(
                        PageText(
                            page_number=page_index + 1,
                            text="",
                            extractor_used="fitz",
                            blocks=None,
                            lines=None,
                            error=f"fitz_page_error: {exc}",
                        )
                    )
        return pages, None
    except Exception as exc:
        return [], f"fitz_open_error: {exc}"


def _extract_with_pdfplumber(path: Path, max_pages: int) -> tuple[list[PageText], str | None]:
    try:
        import pdfplumber
    except ImportError as exc:
        return [], f"pdfplumber unavailable: {exc}"

    pages: list[PageText] = []
    try:
        with pdfplumber.open(path) as pdf:
            page_count = min(max_pages, len(pdf.pages))
            for page_index in range(page_count):
                try:
                    page = pdf.pages[page_index]
                    text = page.extract_text() or ""
                    pages.append(
                        PageText(
                            page_number=page_index + 1,
                            text=text,
                            extractor_used="pdfplumber",
                            blocks=None,
                            lines=None,
                            error=None if text.strip() else "empty_text_from_pdfplumber",
                        )
                    )
                except Exception as exc:
                    pages.append(
                        PageText(
                            page_number=page_index + 1,
                            text="",
                            extractor_used="pdfplumber",
                            blocks=None,
                            lines=None,
                            error=f"pdfplumber_page_error: {exc}",
                        )
                    )
        return pages, None
    except Exception as exc:
        return [], f"pdfplumber_open_error: {exc}"


def _fill_missing_pages_with_pdfplumber(
    path: Path, max_pages: int, fitz_pages: list[PageText]
) -> list[PageText]:
    missing_pages = [page.page_number for page in fitz_pages if not page.text.strip()]
    if not missing_pages:
        return fitz_pages

    plumber_pages, plumber_error = _extract_with_pdfplumber(path, max_pages)
    if not plumber_pages:
        if plumber_error:
            for page in fitz_pages:
                if page.page_number in missing_pages:
                    page.error = plumber_error if page.error is None else f"{page.error}; {plumber_error}"
        return fitz_pages

    plumber_by_page = {page.page_number: page for page in plumber_pages}
    merged_pages: list[PageText] = []
    for fitz_page in fitz_pages:
        plumber_page = plumber_by_page.get(fitz_page.page_number)
        if plumber_page and plumber_page.text.strip():
            merged_pages.append(plumber_page)
        else:
            if plumber_page and plumber_page.error and not fitz_page.error:
                fitz_page.error = plumber_page.error
            merged_pages.append(fitz_page)
    return merged_pages


def _fitz_blocks(page: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_block in page.get_text("blocks") or []:
        if len(raw_block) < 5:
            continue
        x0, y0, x1, y1, text = raw_block[:5]
        blocks.append(
            {
                "bbox": [x0, y0, x1, y1],
                "text": text or "",
            }
        )
    return blocks


def _fitz_lines(page: Any) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    text_dict = page.get_text("dict") or {}
    for block_index, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line_index, line in enumerate(block.get("lines", [])):
            spans = line.get("spans", [])
            line_text = "".join(span.get("text", "") for span in spans)
            lines.append(
                {
                    "bbox": line.get("bbox"),
                    "text": line_text,
                    "block_index": block_index,
                    "line_index": line_index,
                }
            )
    return lines
