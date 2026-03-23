from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable, Sequence

from author_email_match import AuthorEmailPair, match_authors_and_emails
from author_extract import AuthorCandidate, extract_authors_from_pages
from email_extract import EmailCandidate, extract_emails_from_pages
from pdf_extract import PageText, extract_pages


DEFAULT_MAX_PAGES = 2
CN_PUBLIC_EMAIL_DOMAINS = {
    "126.com",
    "163.com",
    "21cn.com",
    "139.com",
    "189.cn",
    "aliyun.com",
    "foxmail.com",
    "qq.com",
    "sina.com",
    "sohu.com",
    "yeah.net",
}
EQUAL_CONTRIBUTION_HINTS = (
    "contributed equally",
    "equal contribution",
    "equal contributions",
    "co-first author",
    "co-first authors",
    "co first author",
    "co first authors",
)


def assemble_structured_output(
    authors: Sequence[AuthorCandidate] | Iterable[AuthorCandidate],
    emails: Sequence[EmailCandidate] | Iterable[EmailCandidate],
    pairs: Sequence[AuthorEmailPair] | Iterable[AuthorEmailPair],
    pages: Sequence[PageText] | None = None,
) -> dict[str, Any]:
    author_list = _sort_authors(list(authors))
    email_list = _sort_emails(list(emails))
    pair_list = _sort_pairs(list(pairs), author_list)

    equal_contribution_detected = _detect_equal_contribution(pages or [])
    first_author = _build_first_author(author_list[0]) if author_list else None
    co_first_authors = _build_co_first_authors(author_list, equal_contribution_detected)

    matched_author_norms = {pair.author_normalized for pair in pair_list}
    matched_email_norms = {pair.email_normalized for pair in pair_list}
    email_regions = {
        pair.email_normalized: classify_email_region(pair.email_normalized)
        for pair in pair_list
    }

    first_author_email = None
    first_author_region = None
    if first_author is not None:
        first_pair = _find_first_author_pair(first_author["author_norm"], pair_list)
        if first_pair is not None:
            first_author_email = first_pair.email_normalized
            first_author_region = email_regions.get(
                first_pair.email_normalized,
                classify_email_region(first_pair.email_normalized),
            )

    authors_payload = [_author_summary(author) for author in author_list]
    emails_payload = [_email_summary(email, email_regions) for email in email_list]
    pairs_payload = [_pair_summary(pair, email_regions) for pair in pair_list]
    shared_emails = _build_shared_emails(pair_list, email_regions)
    unmatched_authors = _build_unmatched_authors(author_list, matched_author_norms)
    unmatched_emails = _build_unmatched_emails(email_list, matched_email_norms)

    stats = {
        "author_count": len(author_list),
        "email_count": len(email_list),
        "pair_count": len(pair_list),
        "shared_email_count": len(shared_emails),
        "unmatched_author_count": len(unmatched_authors),
        "unmatched_email_count": len(unmatched_emails),
        "first_author_found": first_author is not None,
        "has_first_author_email": first_author_email is not None,
    }

    return {
        "authors": authors_payload,
        "first_author": first_author,
        "co_first_authors": co_first_authors,
        "equal_contribution_detected": equal_contribution_detected,
        "emails": emails_payload,
        "pairs": pairs_payload,
        "shared_emails": shared_emails,
        "unmatched_authors": unmatched_authors,
        "unmatched_emails": unmatched_emails,
        "first_author_email": first_author_email,
        "first_author_region": first_author_region,
        "stats": stats,
    }


def assemble_structured_output_from_pdf(
    pdf_path: str | Path,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    pages = extract_pages(pdf_path, max_pages=max_pages)
    authors = extract_authors_from_pages(pages)
    emails = extract_emails_from_pages(pages)
    pairs = match_authors_and_emails(authors, emails, pages=pages)
    return assemble_structured_output(authors, emails, pairs, pages=pages)


def classify_email_region(email: str | None) -> str:
    if not email or "@" not in email:
        return "UNKNOWN"
    domain = email.rsplit("@", 1)[1].strip().lower()
    if not domain:
        return "UNKNOWN"
    if domain.endswith(".cn"):
        return "CN"
    if domain in CN_PUBLIC_EMAIL_DOMAINS:
        return "CN"
    return "OVERSEAS"


def _sort_authors(authors: Sequence[AuthorCandidate]) -> list[AuthorCandidate]:
    return sorted(
        authors,
        key=lambda item: (
            item.author_index if item.author_index is not None else 10**9,
            item.page_number if item.page_number is not None else 10**9,
            item.normalized,
        ),
    )


def _sort_emails(emails: Sequence[EmailCandidate]) -> list[EmailCandidate]:
    return sorted(
        emails,
        key=lambda item: (
            item.page_number if item.page_number is not None else 10**9,
            item.normalized,
        ),
    )


def _sort_pairs(
    pairs: Sequence[AuthorEmailPair],
    authors: Sequence[AuthorCandidate],
) -> list[AuthorEmailPair]:
    author_order = {
        author.normalized: author.author_index if author.author_index is not None else 10**9
        for author in authors
    }
    return sorted(
        pairs,
        key=lambda item: (
            author_order.get(item.author_normalized, 10**9),
            item.page_number if item.page_number is not None else 10**9,
            item.email_normalized,
        ),
    )


def _build_first_author(author: AuthorCandidate) -> dict[str, Any]:
    return {
        "author_raw": author.raw,
        "author_norm": author.normalized,
        "source_page": author.page_number,
        "reason": "first_by_author_order",
        "confidence": author.confidence,
    }


def _author_summary(author: AuthorCandidate) -> dict[str, Any]:
    return {
        "author_raw": author.raw,
        "author_norm": author.normalized,
        "source_page": author.page_number,
        "author_index": author.author_index,
        "markers": list(author.markers),
        "confidence": author.confidence,
        "source_snippet": author.source_snippet,
    }


def _email_summary(
    email: EmailCandidate,
    email_regions: dict[str, str],
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "email": email.normalized,
        "source_page": email.page_number,
        "pattern_type": email.pattern_type,
        "confidence": email.confidence,
        "source_snippet": email.source_snippet,
    }
    if email.normalized in email_regions:
        item["region"] = email_regions[email.normalized]
    return item


def _pair_summary(
    pair: AuthorEmailPair,
    email_regions: dict[str, str],
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "author_norm": pair.author_normalized,
        "email": pair.email_normalized,
        "match_reason": pair.match_reason,
        "source_page": pair.page_number,
        "confidence": pair.confidence,
        "notes": pair.notes,
    }
    region = email_regions.get(pair.email_normalized)
    if region is not None:
        item["region"] = region
    return item


def _build_shared_emails(
    pairs: Sequence[AuthorEmailPair],
    email_regions: dict[str, str],
) -> list[dict[str, Any]]:
    by_email: dict[str, list[AuthorEmailPair]] = {}
    for pair in pairs:
        by_email.setdefault(pair.email_normalized, []).append(pair)

    shared_items: list[dict[str, Any]] = []
    for email, grouped_pairs in by_email.items():
        if len(grouped_pairs) < 2:
            continue
        item: dict[str, Any] = {
            "email": email,
            "author_norms": [pair.author_normalized for pair in grouped_pairs],
            "match_reasons": [pair.match_reason for pair in grouped_pairs],
        }
        region = email_regions.get(email)
        if region is not None:
            item["region"] = region
        shared_items.append(item)
    return sorted(shared_items, key=lambda item: item["email"])


def _build_unmatched_authors(
    authors: Sequence[AuthorCandidate],
    matched_author_norms: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for author in authors:
        if author.normalized in matched_author_norms:
            continue
        items.append(
            {
                "author_norm": author.normalized,
                "reason": "no_confirmed_email_match",
                "author_index": author.author_index,
                "source_page": author.page_number,
            }
        )
    return items


def _build_unmatched_emails(
    emails: Sequence[EmailCandidate],
    matched_email_norms: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for email in emails:
        if email.normalized in matched_email_norms:
            continue
        items.append(
            {
                "email": email.normalized,
                "reason": "no_confirmed_author_match",
                "source_page": email.page_number,
            }
        )
    return items


def _find_first_author_pair(
    first_author_norm: str,
    pairs: Sequence[AuthorEmailPair],
) -> AuthorEmailPair | None:
    for pair in pairs:
        if pair.author_normalized == first_author_norm:
            return pair
    return None


def _detect_equal_contribution(pages: Sequence[PageText]) -> bool:
    if not pages:
        return False
    combined = "\n".join(page.text for page in pages).lower()
    return any(hint in combined for hint in EQUAL_CONTRIBUTION_HINTS)


def _build_co_first_authors(
    authors: Sequence[AuthorCandidate],
    equal_contribution_detected: bool,
) -> list[dict[str, Any]]:
    if not equal_contribution_detected or not authors:
        return []
    first_author = authors[0]
    first_markers = _normalized_markers(first_author.markers)
    if not first_markers:
        return []

    items: list[dict[str, Any]] = []
    for author in authors[1:]:
        if first_markers & _normalized_markers(author.markers):
            items.append(_author_summary(author))
    return items


def _normalized_markers(markers: Sequence[str]) -> set[str]:
    cleaned = {
        marker.strip()
        for marker in markers
        if marker and marker.strip() and not marker.strip().isdigit()
    }
    if cleaned:
        return cleaned
    return {
        marker.strip()
        for marker in markers
        if marker and marker.strip()
    }


__all__ = [
    "assemble_structured_output",
    "assemble_structured_output_from_pdf",
    "classify_email_region",
]
