from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from pdf_extract import PageText, extract_pages


DEFAULT_MAX_PAGES = 2
BASE_CONFIDENCE = 0.98
GROUP_CONFIDENCE = 0.9
OBFUSCATED_CONFIDENCE = 0.78
AMBIGUOUS_GROUP_CONFIDENCE = 0.45
INLINE_GROUP_MAX_LINE_LENGTH = 120

_BASIC_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})(?![A-Za-z0-9._%+\-])",
    re.IGNORECASE,
)
_BRACE_WITH_DOMAIN_RE = re.compile(
    r"\{\s*([^{}@]{1,240}?)\s*\}\s*@\s*([A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
    re.IGNORECASE | re.DOTALL,
)
_BRACE_BODY_RE = re.compile(r"\{\s*([^{}]{1,260}?)\s*\}", re.DOTALL)
_INLINE_GROUP_WITH_DOMAIN_RE = re.compile(
    r"^([A-Za-z0-9._%+\- ]{1,80}(?:\s*[,/]\s*[A-Za-z0-9._%+\- ]{1,80}){1,10})\s*@\s*([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$",
    re.IGNORECASE,
)
_OBFUSCATED_RE = re.compile(
    r"([A-Za-z0-9._%+\-]{1,80})\s*(?:\[at\]|\(at\)|\sat\s)\s*([A-Za-z0-9.\-]{1,120})\s*(?:\[dot\]|\(dot\)|\sdot\s)\s*([A-Za-z]{2,24})",
    re.IGNORECASE,
)
_VALID_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", re.IGNORECASE)
_URL_LIKE_RE = re.compile(r"^(?:https?|ftp)://", re.IGNORECASE)


@dataclass
class EmailCandidate:
    raw: str
    normalized: str
    page_number: int | None
    pattern_type: str
    confidence: float
    source_snippet: str

    def to_dict(self) -> dict:
        return asdict(self)


def extract_emails_from_text(text: str, page_number: int | None = None) -> list[EmailCandidate]:
    normalized_text = _normalize_text(text)
    candidates: list[EmailCandidate] = []
    seen_spans: list[tuple[int, int]] = []

    for match in _BRACE_WITH_DOMAIN_RE.finditer(normalized_text):
        raw = match.group(0)
        local_group = match.group(1)
        domain = match.group(2)
        expanded = _expand_group_tokens(local_group, domain)
        if expanded:
            for email in expanded:
                candidates.append(
                    EmailCandidate(
                        raw=raw,
                        normalized=email,
                        page_number=page_number,
                        pattern_type="grouped_brace_expanded",
                        confidence=GROUP_CONFIDENCE,
                        source_snippet=_build_snippet(normalized_text, match.start(), match.end()),
                    )
                )
        else:
            candidates.append(
                EmailCandidate(
                    raw=raw,
                    normalized=_normalize_group_raw(raw),
                    page_number=page_number,
                    pattern_type="grouped_brace_ambiguous",
                    confidence=AMBIGUOUS_GROUP_CONFIDENCE,
                    source_snippet=_build_snippet(normalized_text, match.start(), match.end()),
                )
            )
        seen_spans.append(match.span())

    for match in _BRACE_BODY_RE.finditer(normalized_text):
        if _overlaps(match.span(), seen_spans):
            continue
        body = match.group(1)
        expanded = _expand_brace_body_with_embedded_domain(body)
        if not expanded:
            continue
        raw = match.group(0)
        for candidate in expanded:
            candidates.append(
                EmailCandidate(
                    raw=raw,
                    normalized=candidate,
                    page_number=page_number,
                    pattern_type="grouped_brace_embedded_domain",
                    confidence=GROUP_CONFIDENCE,
                    source_snippet=_build_snippet(normalized_text, match.start(), match.end()),
                )
            )
        seen_spans.append(match.span())

    candidates.extend(_extract_inline_grouped_candidates(normalized_text, page_number))

    for match in _OBFUSCATED_RE.finditer(normalized_text):
        raw = match.group(0)
        normalized = _normalize_email(f"{match.group(1)}@{match.group(2)}.{match.group(3)}")
        if _is_valid_email(normalized):
            candidates.append(
                EmailCandidate(
                    raw=raw,
                    normalized=normalized,
                    page_number=page_number,
                    pattern_type="obfuscated_email",
                    confidence=OBFUSCATED_CONFIDENCE,
                    source_snippet=_build_snippet(normalized_text, match.start(), match.end()),
                )
            )

    for match in _BASIC_EMAIL_RE.finditer(normalized_text):
        raw = match.group(1)
        normalized = _normalize_email(raw)
        if not _is_valid_email(normalized):
            continue
        candidates.append(
            EmailCandidate(
                raw=raw,
                normalized=normalized,
                page_number=page_number,
                pattern_type="basic_email",
                confidence=BASE_CONFIDENCE,
                source_snippet=_build_snippet(normalized_text, match.start(), match.end()),
            )
        )

    return _dedupe_candidates(candidates)


def extract_emails_from_pages(pages: Iterable[PageText]) -> list[EmailCandidate]:
    aggregated: list[EmailCandidate] = []
    for page in pages:
        try:
            aggregated.extend(extract_emails_from_text(page.text, page_number=page.page_number))
        except Exception:
            continue
    return _dedupe_candidates(aggregated)


def extract_emails_from_pdf(pdf_path: str | Path, max_pages: int = DEFAULT_MAX_PAGES) -> list[EmailCandidate]:
    pages = extract_pages(pdf_path, max_pages=max_pages)
    return extract_emails_from_pages(pages)


def _normalize_text(text: str) -> str:
    cleaned = text.replace("\u00a0", " ")
    cleaned = cleaned.replace("\u200b", "")
    cleaned = cleaned.replace("\ufb01", "fi").replace("\ufb02", "fl")
    cleaned = re.sub(r"(?<=@)\s+(?=[A-Za-z0-9])", "", cleaned)
    cleaned = re.sub(r"(?<=\.)\s+(?=[A-Za-z])", "", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z0-9._%+\-])\s*@\s*(?=[A-Za-z0-9])", "@", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z0-9])\s*\.\s*(?=[A-Za-z])", ".", cleaned)
    cleaned = re.sub(r"\{\s+", "{", cleaned)
    cleaned = re.sub(r"\s+\}", "}", cleaned)
    cleaned = re.sub(r"\s*,\s*", ",", cleaned)
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    return cleaned


def _extract_inline_grouped_candidates(text: str, page_number: int | None) -> list[EmailCandidate]:
    candidates: list[EmailCandidate] = []
    cursor = 0
    for line in text.splitlines():
        line_start = cursor
        line_end = cursor + len(line)
        cursor = line_end + 1
        candidate_line = line.strip().strip(";,. ")
        if not candidate_line:
            continue
        if "{" in candidate_line or "}" in candidate_line:
            continue
        if candidate_line.count("@") != 1:
            continue
        if len(candidate_line) > INLINE_GROUP_MAX_LINE_LENGTH:
            continue
        match = _INLINE_GROUP_WITH_DOMAIN_RE.match(candidate_line)
        if not match:
            continue
        local_group = match.group(1)
        domain = match.group(2)
        expanded = _expand_group_tokens(local_group, domain)
        if not expanded:
            continue
        pattern_type = "grouped_slash_expanded" if "/" in local_group else "grouped_inline_expanded"
        for email in expanded:
            candidates.append(
                EmailCandidate(
                    raw=candidate_line,
                    normalized=email,
                    page_number=page_number,
                    pattern_type=pattern_type,
                    confidence=GROUP_CONFIDENCE,
                    source_snippet=_build_snippet(text, line_start, line_end),
                )
            )
    return candidates


def _expand_group_tokens(local_group: str, domain: str) -> list[str]:
    group_body = local_group.replace("\n", " ")
    if "," in group_body:
        parts = group_body.split(",")
    elif "/" in group_body:
        parts = group_body.split("/")
    else:
        return []

    emails: list[str] = []
    for part in parts:
        token = _clean_local_part(part)
        if not token:
            return []
        if token.count(".") >= 2:
            return []
        normalized = _normalize_email(f"{token}@{domain}")
        if not _is_valid_email(normalized):
            return []
        emails.append(normalized)
    return emails


def _expand_brace_body_with_embedded_domain(body: str) -> list[str]:
    compact = body.replace("\n", " ")
    parts = [part.strip() for part in compact.split(",") if part.strip()]
    email_parts = [_normalize_email(part) for part in parts if "@" in part]
    if len(email_parts) != 1:
        return []

    embedded_email = email_parts[0]
    if not _is_valid_email(embedded_email):
        return []
    domain = embedded_email.split("@", 1)[1]

    expanded: list[str] = []
    for part in parts:
        token = part.strip()
        if "@" in token:
            normalized = _normalize_email(token)
        else:
            local = _clean_local_part(token)
            if not local:
                return []
            normalized = _normalize_email(f"{local}@{domain}")
        if not _is_valid_email(normalized):
            return []
        expanded.append(normalized)
    return expanded


def _clean_local_part(token: str) -> str:
    cleaned = token.strip().strip(";,.!?) ]")
    cleaned = cleaned.strip("([<")
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace("\n", "")
    cleaned = cleaned.lower()
    if not cleaned:
        return ""
    if "@" in cleaned:
        return cleaned.split("@", 1)[0]
    if re.search(r"[^a-z0-9._%+\-]", cleaned):
        return ""
    return cleaned


def _normalize_email(value: str) -> str:
    normalized = value.strip().strip(";,.!?) ]")
    normalized = normalized.strip("([<")
    normalized = normalized.replace(" ", "")
    normalized = normalized.replace("\n", "")
    normalized = normalized.lower()
    local_part, sep, domain = normalized.partition("@")
    if sep and "." in local_part:
        parts = local_part.split(".")
        if len(parts) >= 3 and parts[0] in {"india", "china", "australia", "singapore"}:
            candidate = ".".join(parts[1:]) + "@" + domain
            if _VALID_EMAIL_RE.match(candidate):
                normalized = candidate
    return normalized


def _normalize_group_raw(raw: str) -> str:
    return re.sub(r"\s+", "", raw).lower()


def _is_valid_email(value: str) -> bool:
    if not value or "@" not in value or _URL_LIKE_RE.match(value):
        return False
    if not _VALID_EMAIL_RE.match(value):
        return False
    return not _is_noise_email(value)


def _is_noise_email(value: str) -> bool:
    local_part, _, domain = value.partition("@")
    if domain == "acm.org" and ("permission" in local_part or "copyright" in local_part):
        return True
    return False


def _build_snippet(text: str, start: int, end: int, radius: int = 60) -> str:
    snippet = text[max(0, start - radius): min(len(text), end + radius)]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:220]


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    for left, right in spans:
        if start < right and end > left:
            return True
    return False


def _dedupe_candidates(candidates: list[EmailCandidate]) -> list[EmailCandidate]:
    deduped: dict[str, EmailCandidate] = {}
    for candidate in candidates:
        key = candidate.normalized
        current = deduped.get(key)
        if current is None:
            deduped[key] = candidate
            continue
        current_page = current.page_number if current.page_number is not None else 10**9
        candidate_page = candidate.page_number if candidate.page_number is not None else 10**9
        if candidate_page < current_page:
            deduped[key] = candidate
            continue
        if candidate_page == current_page and candidate.confidence > current.confidence:
            deduped[key] = candidate
    return sorted(deduped.values(), key=lambda item: ((item.page_number or 10**9), item.normalized))
