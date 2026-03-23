from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assemble_structured_output import assemble_structured_output
from author_email_match import AuthorEmailPair, match_authors_and_emails
from author_extract import AuthorCandidate, extract_authors_from_pages
from email_extract import EmailCandidate, extract_emails_from_pages
from pdf_extract import PDFExtractError, PageText, extract_pages


DEFAULT_MAX_PAGES = 2
LOGGER = logging.getLogger(__name__)
ZERO_STATS = {
    "author_count": 0,
    "email_count": 0,
    "pair_count": 0,
    "shared_email_count": 0,
    "unmatched_author_count": 0,
    "unmatched_email_count": 0,
    "first_author_found": False,
    "has_first_author_email": False,
}


class PipelineError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        stats: dict[str, Any] | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(detail or message)
        self.code = code
        self.message = message
        self.stats = dict(stats or ZERO_STATS)
        self.detail = detail or message


@dataclass
class PipelineRunResult:
    pdf_path: str
    pages: list[PageText]
    authors: list[AuthorCandidate]
    emails: list[EmailCandidate]
    pairs: list[AuthorEmailPair]
    structured_output: dict[str, Any]
    stats: dict[str, Any]
    debug_info: dict[str, Any] | None = None


def run_pipeline(
    pdf_path: str | Path,
    max_pages: int = DEFAULT_MAX_PAGES,
    debug: bool = False,
) -> PipelineRunResult:
    try:
        pages = extract_pages(pdf_path, max_pages=max_pages)
    except (FileNotFoundError, ValueError, PDFExtractError) as exc:
        raise PipelineError(
            "PARSE_FAILED",
            "pdf parsing or extraction failed",
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise PipelineError(
            "PARSE_FAILED",
            "pdf parsing or extraction failed",
            detail=str(exc),
        ) from exc

    if not _has_parse_signal(pages):
        raise PipelineError(
            "PARSE_FAILED",
            "pdf parsing or extraction failed",
            detail="no readable text or page metadata extracted",
        )

    try:
        authors = extract_authors_from_pages(pages)
        emails = extract_emails_from_pages(pages)
        partial_stats = _partial_stats(authors, emails)
    except Exception as exc:
        raise PipelineError(
            "PARSE_FAILED",
            "pdf parsing or extraction failed",
            detail=str(exc),
        ) from exc

    LOGGER.info(
        "pipeline extraction summary pdf=%s authors=%s emails=%s first_author_found=%s",
        pdf_path,
        len(authors),
        len(emails),
        bool(authors),
    )

    if not emails:
        raise PipelineError(
            "NO_EMAIL_FOUND",
            "no email candidate found",
            stats=partial_stats,
            detail="email extraction returned zero candidates",
        )

    try:
        pairs = match_authors_and_emails(authors, emails, pages=pages)
        structured_output = assemble_structured_output(authors, emails, pairs, pages=pages)
    except Exception as exc:
        raise PipelineError(
            "PARSE_FAILED",
            "pdf parsing or extraction failed",
            stats=partial_stats,
            detail=str(exc),
        ) from exc

    stats = dict(structured_output.get("stats") or ZERO_STATS)
    LOGGER.info(
        "pipeline assembly summary pdf=%s pair_count=%s shared_email_count=%s first_author_email=%s",
        pdf_path,
        stats.get("pair_count", 0),
        stats.get("shared_email_count", 0),
        structured_output.get("first_author_email") is not None,
    )

    debug_info = None
    if debug:
        debug_info = {
            "page_count": len(pages),
            "extractors": [page.extractor_used for page in pages],
            "page_errors": [page.error for page in pages if page.error],
        }

    return PipelineRunResult(
        pdf_path=str(Path(pdf_path)),
        pages=pages,
        authors=authors,
        emails=emails,
        pairs=pairs,
        structured_output=structured_output,
        stats=stats,
        debug_info=debug_info,
    )


def _has_parse_signal(pages: list[PageText]) -> bool:
    for page in pages:
        if page.text.strip():
            return True
        if page.blocks or page.lines:
            return True
    return False


def _partial_stats(
    authors: list[AuthorCandidate],
    emails: list[EmailCandidate],
) -> dict[str, Any]:
    return {
        "author_count": len(authors),
        "email_count": len(emails),
        "pair_count": 0,
        "shared_email_count": 0,
        "unmatched_author_count": len(authors),
        "unmatched_email_count": len(emails),
        "first_author_found": bool(authors),
        "has_first_author_email": False,
    }


__all__ = [
    "DEFAULT_MAX_PAGES",
    "PipelineError",
    "PipelineRunResult",
    "ZERO_STATS",
    "run_pipeline",
]
