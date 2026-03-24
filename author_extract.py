from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from pdf_extract import PageText, extract_pages


DEFAULT_MAX_PAGES = 2
MAX_TOP_LINES = 40
LINE_CONFIDENCE = 0.94
BLOCK_CONFIDENCE = 0.82

_CONNECTOR_TOKENS = {"de", "del", "der", "di", "dos", "la", "le", "van", "von"}
_NAME_TOKEN_RE = r"(?:[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’`\-]*\.?|[A-Z]\.)"
_FULL_NAME_RE = re.compile(
    rf"^(?P<name>{_NAME_TOKEN_RE}(?:\s+(?:{'|'.join(sorted(_CONNECTOR_TOKENS))}\s+)?{_NAME_TOKEN_RE}){{1,5}})"
    r"(?P<suffix>(?:\s*(?:\d+(?:<NUMCOMMA>\d+)*|[\*\u2217\u2020\u2021\u00a7\u00b6\u2021xXB#]+|[A-HJ-Z]))*)\s*$"
)
_STOP_PATTERNS = (
    "abstract",
    "introduction",
    "contents",
    "keywords",
    "index terms",
    "figure ",
    "table ",
    "1 introduction",
    "i. introduction",
)
_NON_AUTHOR_PHRASES = (
    "corresponding author",
    "correspondence:",
    "contributed equally",
    "these authors contributed equally",
    "co-first author",
    "co-first authors",
    "equal contribution",
    "project lead",
    "projectpage",
    "repository",
    "tutorial",
    "preprint submitted",
    "draft:",
    "copyright",
)
_AFFILIATION_KEYWORDS = (
    "academy",
    "center",
    "centre",
    "college",
    "cloud",
    "company",
    "corporation",
    "department",
    "division",
    "faculty",
    "group",
    "hospital",
    "institute",
    "laboratory",
    "lab",
    "school",
    "technology",
    "university",
)
_MARGIN_NOISE_PATTERNS = (
    "arxiv:",
    "preprint",
)
_LOCATION_HINTS = (
    "australia",
    "canada",
    "china",
    "france",
    "germany",
    "hong kong",
    "israel",
    "italy",
    "korea",
    "province",
    "singapore",
    "south korea",
    "uk",
    "usa",
)
_EMAIL_OR_URL_RE = re.compile(r"@|https?://|www\.", re.IGNORECASE)
_DIGIT_COMMA_DIGIT_RE = re.compile(r"(?<=\d),(?=\d)")
_MARKER_COMMA_REWRITES = (
    (re.compile(r"(?<=\d),(?=[\*\u2217\u2020\u2021\u00a7\u00b6xXB#])"), ""),
    (re.compile(r"(?<=[\*\u2217\u2020\u2021\u00a7\u00b6xXB#]),(?=[\*\u2217\u2020\u2021\u00a7\u00b6xXB#])"), ""),
)
_INLINE_SEPARATOR_REWRITES = (
    (re.compile(r"(?<=[\*\u2217\u2020\u2021\u00a7\u00b6xXB#])(?=[A-Z][a-z])"), ", "),
    (re.compile(r"(\d[\*\u2217\u2020\u2021\u00a7\u00b6xXB#]{0,3})(?=[A-Z][a-z])"), r"\1, "),
)
_AFFILIATION_LINE_RE = re.compile(r"^\s*([a-z])(?:\s|[A-Z])")
_ATTACHED_MARKER_SYMBOLS_RE = re.compile(r"[\*\u2217\u2020\u2021\u00a7\u00b6xXB#]")
_ATTACHED_MARKER_TRAILER_RE = re.compile(
    r"^(?P<base>.*\b[A-Za-z][A-Za-z'鈥檂\-]*?)(?P<attached>[a-z])(?P<trailer>(?:\s*,\s*(?:[a-z]|[\*\u2217\u2020\u2021\u00a7\u00b6xXB#])+)+)\s*$"
)
_TERMINAL_ATTACHED_MARKER_RE = re.compile(
    r"^(?P<base>.*\b[A-Za-z][A-Za-z'鈥檂\-]*?)(?P<attached>[a-z])\s*$"
)


@dataclass
class AuthorCandidate:
    raw: str
    normalized: str
    page_number: int | None
    author_index: int | None
    markers: list[str]
    confidence: float
    source_snippet: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _LineEntry:
    text: str
    page_number: int
    source_snippet: str
    y0: float | None = None
    x0: float | None = None


def extract_authors_from_text(text: str) -> list[AuthorCandidate]:
    line_entries = [
        _LineEntry(
            text=line,
            page_number=1,
            source_snippet=_compact_snippet(line),
        )
        for line in text.splitlines()
    ]
    parsed = _extract_from_line_entries(line_entries, base_confidence=LINE_CONFIDENCE)
    return _reindex_candidates(parsed)


def extract_authors_from_pages(pages: Iterable[PageText]) -> list[AuthorCandidate]:
    page_list = list(pages)
    if not page_list:
        return []

    best_result: list[AuthorCandidate] = []
    for page in page_list:
        line_entries = _page_line_entries(page)
        parsed_from_lines = _extract_from_line_entries(line_entries, base_confidence=LINE_CONFIDENCE)
        if parsed_from_lines:
            return _reindex_candidates(parsed_from_lines)

        parsed_from_blocks = _extract_from_blocks(page)
        if parsed_from_blocks and len(parsed_from_blocks) > len(best_result):
            best_result = parsed_from_blocks

    return _reindex_candidates(best_result)


def extract_authors_from_pdf(
    pdf_path: str | Path,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[AuthorCandidate]:
    pages = extract_pages(pdf_path, max_pages=max_pages)
    return extract_authors_from_pages(pages)


def _extract_from_line_entries(
    line_entries: list[_LineEntry],
    base_confidence: float,
) -> list[AuthorCandidate]:
    scoped_lines = _scoped_top_lines(line_entries)
    if not scoped_lines:
        return []

    affiliation_markers = _detect_affiliation_markers(scoped_lines)
    attached_marker_mode = _has_attached_marker_mode(scoped_lines, affiliation_markers)
    parsed_by_line = [
        _parse_author_line(
            line.text,
            affiliation_markers=affiliation_markers,
            allow_terminal_affiliation_marker=attached_marker_mode,
        )
        for line in scoped_lines
    ]
    start_index = _find_author_start(scoped_lines, parsed_by_line)
    if start_index is None:
        return []

    candidates: list[AuthorCandidate] = []
    author_chunks: list[str] = []
    non_author_run = 0
    for index in range(start_index, len(scoped_lines)):
        line = scoped_lines[index]
        parsed = parsed_by_line[index]
        if not parsed:
            if _is_ignorable_meta_line(line.text):
                continue
            if _is_body_text_line(line.text):
                break
            non_author_run += 1
            if non_author_run >= 4:
                break
            continue
        non_author_run = 0
        author_chunks.append(line.text)
        for raw, normalized, markers in parsed:
            candidates.append(
                AuthorCandidate(
                    raw=raw,
                    normalized=normalized,
                    page_number=line.page_number,
                    author_index=None,
                    markers=markers,
                    confidence=_candidate_confidence(base_confidence, markers, raw),
                    source_snippet=line.source_snippet,
                )
            )
    deduped = _dedupe_candidates(candidates)
    if author_chunks:
        combined_text = ", ".join(_merge_author_chunks(author_chunks))
        combined_parsed = _parse_author_line(
            combined_text,
            affiliation_markers=affiliation_markers,
            allow_terminal_affiliation_marker=attached_marker_mode,
        )
        if len(combined_parsed) > len(deduped):
            combined_candidates = [
                AuthorCandidate(
                    raw=raw,
                    normalized=normalized,
                    page_number=scoped_lines[start_index].page_number,
                    author_index=None,
                    markers=markers,
                    confidence=_candidate_confidence(base_confidence, markers, raw),
                    source_snippet=_compact_snippet(combined_text),
                )
                for raw, normalized, markers in combined_parsed
            ]
            deduped = _dedupe_candidates(combined_candidates)
    return deduped


def _extract_from_blocks(page: PageText) -> list[AuthorCandidate]:
    if not page.blocks:
        return []

    stop_y = _find_stop_y(_page_line_entries(page))
    affiliation_markers = _detect_affiliation_markers(_page_line_entries(page))
    attached_marker_mode = bool(affiliation_markers)
    block_candidates: list[AuthorCandidate] = []
    blocks = sorted(page.blocks, key=lambda item: _bbox_key(item.get("bbox")))
    for block in blocks:
        text = _normalize_text(block.get("text") or "")
        if not text.strip():
            continue
        bbox = block.get("bbox")
        if stop_y is not None and bbox and len(bbox) >= 2 and bbox[1] >= stop_y:
            break
        if _is_margin_noise(text):
            continue
        for raw, normalized, markers in _parse_author_line(
            text,
            affiliation_markers=affiliation_markers,
            allow_terminal_affiliation_marker=attached_marker_mode,
        ):
            block_candidates.append(
                AuthorCandidate(
                    raw=raw,
                    normalized=normalized,
                    page_number=page.page_number,
                    author_index=None,
                    markers=markers,
                    confidence=_candidate_confidence(BLOCK_CONFIDENCE, markers, raw),
                    source_snippet=_compact_snippet(text),
                )
            )
    return _dedupe_candidates(block_candidates)


def _page_line_entries(page: PageText) -> list[_LineEntry]:
    if page.lines:
        ordered_lines = sorted(
            page.lines,
            key=lambda item: (
                item.get("bbox", [10**9, 10**9])[1] if item.get("bbox") else 10**9,
                item.get("bbox", [10**9, 10**9])[0] if item.get("bbox") else 10**9,
                item.get("block_index", 10**9),
                item.get("line_index", 10**9),
            ),
        )
        return [
            _LineEntry(
                text=item.get("text") or "",
                page_number=page.page_number,
                source_snippet=_compact_snippet(item.get("text") or ""),
                y0=item.get("bbox", [None, None])[1] if item.get("bbox") else None,
                x0=item.get("bbox", [None, None])[0] if item.get("bbox") else None,
            )
            for item in ordered_lines
        ]

    entries: list[_LineEntry] = []
    for line in page.text.splitlines():
        entries.append(
            _LineEntry(
                text=line,
                page_number=page.page_number,
                source_snippet=_compact_snippet(line),
            )
        )
    return entries


def _scoped_top_lines(line_entries: list[_LineEntry]) -> list[_LineEntry]:
    scoped: list[_LineEntry] = []
    stop_y = _find_stop_y(line_entries)
    for line in line_entries:
        text = _normalize_text(line.text)
        if not text.strip():
            continue
        if len(scoped) >= MAX_TOP_LINES:
            break
        if line.y0 is not None and stop_y is not None and line.y0 >= stop_y:
            break
        if _is_margin_noise(text):
            continue
        scoped.append(
            _LineEntry(
                text=text,
                page_number=line.page_number,
                source_snippet=line.source_snippet or _compact_snippet(text),
                y0=line.y0,
                x0=line.x0,
            )
        )
    return scoped


def _find_stop_y(line_entries: list[_LineEntry]) -> float | None:
    for line in line_entries:
        text = _normalize_text(line.text)
        if _is_stop_line(text):
            return line.y0
    return None


def _parse_author_line(
    text: str,
    *,
    affiliation_markers: set[str] | None = None,
    allow_terminal_affiliation_marker: bool = False,
) -> list[tuple[str, str, list[str]]]:
    normalized = _normalize_text(text)

    prefix_author = _parse_affiliation_tail_author_line(
        normalized,
        affiliation_markers=affiliation_markers or set(),
        allow_terminal_affiliation_marker=allow_terminal_affiliation_marker,
    )
    if prefix_author:
        return _dedupe_line_results(prefix_author)

    if not _looks_like_author_carrier(normalized):
        return []

    prepared = _prepare_author_line(normalized)
    explicit_segments = _split_explicit_segments(prepared)
    terminal_marker_mode = _should_strip_terminal_affiliation_markers(
        explicit_segments,
        affiliation_markers or set(),
        allow_terminal_affiliation_marker=allow_terminal_affiliation_marker,
    )

    results: list[tuple[str, str, list[str]]] = []
    for segment in explicit_segments:
        results.extend(
            _parse_author_segment(
                segment,
                affiliation_markers=affiliation_markers or set(),
                allow_terminal_affiliation_marker=terminal_marker_mode,
            )
        )

    if results:
        return _dedupe_line_results(results)

    return _dedupe_line_results(
        _parse_author_segment(
            prepared,
            affiliation_markers=affiliation_markers or set(),
            allow_terminal_affiliation_marker=terminal_marker_mode,
        )
    )


def _prepare_author_line(text: str) -> str:
    prepared = _DIGIT_COMMA_DIGIT_RE.sub("<NUMCOMMA>", text)
    for pattern, replacement in _MARKER_COMMA_REWRITES:
        prepared = pattern.sub(replacement, prepared)
    prepared = re.sub(r"\s*&\s*", ", ", prepared)
    prepared = re.sub(r"\s+\band\b\s+", ", ", prepared, flags=re.IGNORECASE)
    for pattern, replacement in _INLINE_SEPARATOR_REWRITES:
        prepared = pattern.sub(replacement, prepared)
    prepared = prepared.replace("\u2022", ", ")
    prepared = re.sub(r"\s+", " ", prepared)
    return prepared.strip(" ,;")


def _split_explicit_segments(text: str) -> list[str]:
    segments = [text]
    splitters = [
        re.compile(r";\s+"),
        re.compile(r",\s+(?=[A-Z])"),
    ]
    for splitter in splitters:
        next_segments: list[str] = []
        for segment in segments:
            parts = [part.strip() for part in splitter.split(segment) if part.strip()]
            next_segments.extend(parts or [segment])
        segments = next_segments
    return segments


def _parse_author_segment(
    segment: str,
    *,
    affiliation_markers: set[str],
    allow_terminal_affiliation_marker: bool,
) -> list[tuple[str, str, list[str]]]:
    cleaned = segment.strip(" ,;")
    if not cleaned or not _looks_like_author_carrier(cleaned):
        return []

    sanitized, attached_markers = _strip_attached_marker_suffix(
        cleaned,
        affiliation_markers=affiliation_markers,
        allow_terminal_affiliation_marker=allow_terminal_affiliation_marker,
    )

    single = _parse_single_author(sanitized)
    if single:
        raw, normalized, markers = single
        return [(raw, normalized, _merge_marker_lists(attached_markers, markers))]

    multi = _parse_multiple_authors(sanitized)
    if multi:
        if attached_markers and len(multi) == 1:
            raw, normalized, markers = multi[0]
            return [(raw, normalized, _merge_marker_lists(attached_markers, markers))]
        return multi

    return []


def _parse_affiliation_tail_author_line(
    text: str,
    *,
    affiliation_markers: set[str],
    allow_terminal_affiliation_marker: bool,
) -> list[tuple[str, str, list[str]]]:
    if "," not in text:
        return []

    first_segment, _, tail = text.partition(",")
    if not tail.strip():
        return []

    tail_lower = tail.lower()
    if not _has_affiliation_or_location_signal(tail_lower):
        return []

    parsed = _parse_author_segment(
        first_segment.strip(),
        affiliation_markers=affiliation_markers,
        allow_terminal_affiliation_marker=allow_terminal_affiliation_marker,
    )
    if len(parsed) == 1:
        return parsed
    return []


def _parse_single_author(text: str) -> tuple[str, str, list[str]] | None:
    match = _FULL_NAME_RE.match(text)
    if not match:
        return None
    author = _build_author_from_match(match)
    if not author:
        return None
    if _trailing_noise(text, [author[0]]):
        return None
    return author


def _parse_multiple_authors(text: str) -> list[tuple[str, str, list[str]]]:
    results: list[tuple[str, str, list[str]]] = []
    cursor = 0
    text_length = len(text)
    while cursor < text_length:
        remaining = text[cursor:].lstrip(" ,;/")
        cursor = text_length - len(remaining)
        if not remaining:
            break

        match = _match_author_prefix(remaining)
        if not match:
            return []

        author = _build_author_from_match(match)
        if not author:
            return []

        raw, _, _ = author
        results.append(author)
        cursor += match.end()

    if len(results) <= 1:
        return []
    if _trailing_noise(text, [item[0] for item in results]):
        return []
    return results


def _match_author_prefix(text: str) -> re.Match[str] | None:
    for end_index in range(len(text), 0, -1):
        candidate = text[:end_index].rstrip(" ,;/")
        match = _FULL_NAME_RE.match(candidate)
        if not match:
            continue
        next_text = text[len(candidate):]
        if next_text and not re.match(r"^[\s,;/]+", next_text):
            continue
        return match
    return None


def _build_author_from_match(match: re.Match[str]) -> tuple[str, str, list[str]] | None:
    raw_name = match.group("name").strip()
    suffix = (match.group("suffix") or "").replace("<NUMCOMMA>", ",")
    name_tokens = raw_name.split()
    if len(name_tokens) >= 3 and re.fullmatch(r"[A-HJ-Z]", name_tokens[-1]):
        suffix = f" {name_tokens[-1]}{suffix}"
        raw_name = " ".join(name_tokens[:-1])
    raw = f"{raw_name}{suffix}".strip()
    normalized = _normalize_person_like_name(_normalize_author_name(raw_name))
    markers = _extract_markers(suffix)
    if not _is_person_name(normalized):
        return None
    return raw, normalized, markers


def _extract_markers(suffix: str) -> list[str]:
    if not suffix:
        return []
    markers: list[str] = []
    for marker in re.findall(r"\d+(?:,\d+)*|[\*\u2217\u2020\u2021\u00a7\u00b6xXB#]+|[A-HJ-Z]", suffix):
        normalized = marker.strip()
        if normalized:
            markers.append(normalized)
    return markers


def _normalize_author_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value)
    normalized = normalized.replace("`", "").replace("’", "").replace("'", "")
    return normalized.strip(" ,;")


def _looks_like_author_carrier(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if re.match(r"^\d+\s*[A-Z]", text):
        return False
    if "," in text and any(hint in lowered for hint in _LOCATION_HINTS):
        return False
    if _EMAIL_OR_URL_RE.search(text):
        return False
    if any(phrase in lowered for phrase in _NON_AUTHOR_PHRASES):
        return False
    if any(keyword in lowered for keyword in _AFFILIATION_KEYWORDS):
        return False
    if _is_stop_line(text):
        return False
    if re.fullmatch(r"[A-Z\s]{2,}", text) and " " not in text.strip():
        return False
    return True


def _has_affiliation_or_location_signal(text: str) -> bool:
    return any(keyword in text for keyword in _AFFILIATION_KEYWORDS) or any(
        hint in text for hint in _LOCATION_HINTS
    )


def _normalize_person_like_name(value: str) -> str:
    tokens = value.split()
    alpha_tokens = [re.sub(r"[^A-Za-z]", "", token) for token in tokens]
    if alpha_tokens and all(token.isupper() for token in alpha_tokens if len(token) > 1):
        return " ".join(
            token.lower() if token.lower() in _CONNECTOR_TOKENS else token.title()
            for token in tokens
        ).strip(" ,;")
    return value


def _find_author_start(
    scoped_lines: list[_LineEntry],
    parsed_by_line: list[list[tuple[str, str, list[str]]]],
) -> int | None:
    for index, parsed in enumerate(parsed_by_line):
        if parsed and _is_strong_author_line(scoped_lines[index].text, parsed):
            return index
    for index, parsed in enumerate(parsed_by_line):
        if parsed and index > 0:
            return index
    for index, parsed in enumerate(parsed_by_line):
        if parsed:
            return index
    return None


def _is_strong_author_line(
    text: str,
    parsed: list[tuple[str, str, list[str]]],
) -> bool:
    if len(parsed) >= 2:
        return True
    if any(markers for _, _, markers in parsed):
        return True
    if "," in text or ";" in text:
        return True
    return False


def _is_stop_line(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    if lowered in {"abstract", "contents"}:
        return True
    if lowered.startswith("abstract ") or lowered.startswith("keywords"):
        return True
    if any(lowered.startswith(pattern) for pattern in _STOP_PATTERNS):
        return True
    return bool(re.match(r"^(?:\d+|[ivx]+)\s+[a-z]", lowered))


def _is_ignorable_meta_line(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    if _EMAIL_OR_URL_RE.search(text):
        return True
    if any(keyword in lowered for keyword in _AFFILIATION_KEYWORDS):
        return True
    if any(phrase in lowered for phrase in _NON_AUTHOR_PHRASES):
        return True
    if re.search(
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
        lowered,
    ):
        return True
    return False


def _is_body_text_line(text: str) -> bool:
    tokens = re.findall(r"[A-Za-z]+", text)
    if len(tokens) < 8:
        return False
    lowered_tokens = [token.lower() for token in tokens]
    common_words = {"the", "of", "and", "for", "with", "that", "this", "from", "into", "within"}
    return any(token in common_words for token in lowered_tokens)


def _is_margin_noise(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    if any(pattern in lowered for pattern in _MARGIN_NOISE_PATTERNS):
        return True
    return lowered.isdigit()


def _is_person_name(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if lowered in _LOCATION_HINTS:
        return False
    if any(keyword in lowered for keyword in _AFFILIATION_KEYWORDS):
        return False
    if any(phrase in lowered for phrase in _NON_AUTHOR_PHRASES):
        return False
    tokens = value.split()
    if len(tokens) < 2 or len(tokens) > 6:
        return False
    if any(not _is_name_token(token) for token in tokens):
        return False
    return True


def _is_name_token(token: str) -> bool:
    cleaned = token.strip(".,")
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in _CONNECTOR_TOKENS:
        return True
    if re.fullmatch(_NAME_TOKEN_RE, cleaned):
        return True
    return False


def _trailing_noise(text: str, raw_values: list[str]) -> bool:
    remainder = text
    for raw in raw_values:
        index = remainder.find(raw)
        if index == -1:
            continue
        remainder = remainder[index + len(raw):]
    compact = remainder.strip(" ,;/")
    if not compact:
        return False
    compact_lower = compact.lower()
    if compact_lower in {"and"}:
        return False
    return any(keyword in compact_lower for keyword in _AFFILIATION_KEYWORDS + _NON_AUTHOR_PHRASES) or bool(
        _EMAIL_OR_URL_RE.search(compact)
    )


def _dedupe_line_results(
    items: list[tuple[str, str, list[str]]],
) -> list[tuple[str, str, list[str]]]:
    deduped: list[tuple[str, str, list[str]]] = []
    seen: set[str] = set()
    for raw, normalized, markers in items:
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((raw.replace("<NUMCOMMA>", ","), normalized, markers))
    return deduped


def _dedupe_candidates(candidates: list[AuthorCandidate]) -> list[AuthorCandidate]:
    deduped: dict[str, AuthorCandidate] = {}
    order: list[str] = []
    for candidate in candidates:
        key = candidate.normalized.casefold()
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = candidate
            order.append(key)
            continue

        existing_page = existing.page_number if existing.page_number is not None else 10**9
        candidate_page = candidate.page_number if candidate.page_number is not None else 10**9
        if candidate_page < existing_page:
            deduped[key] = candidate
        elif candidate_page == existing_page and candidate.confidence > existing.confidence:
            deduped[key] = candidate

        merged_markers = list(dict.fromkeys(existing.markers + candidate.markers))
        deduped[key].markers = merged_markers
    return [deduped[key] for key in order]


def _reindex_candidates(candidates: list[AuthorCandidate]) -> list[AuthorCandidate]:
    indexed: list[AuthorCandidate] = []
    for index, candidate in enumerate(candidates):
        indexed.append(
            AuthorCandidate(
                raw=candidate.raw,
                normalized=candidate.normalized,
                page_number=candidate.page_number,
                author_index=index,
                markers=candidate.markers,
                confidence=candidate.confidence,
                source_snippet=candidate.source_snippet,
            )
        )
    return indexed


def _normalize_text(text: str) -> str:
    cleaned = text.replace("\u00a0", " ")
    cleaned = cleaned.replace("\u200b", "")
    cleaned = cleaned.replace("\ufb01", "fi").replace("\ufb02", "fl")
    cleaned = cleaned.replace("\u2217", "*")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _compact_snippet(text: str, limit: int = 220) -> str:
    snippet = re.sub(r"\s+", " ", text).strip()
    return snippet[:limit]


def _detect_affiliation_markers(line_entries: Sequence[_LineEntry]) -> set[str]:
    markers: set[str] = set()
    for line in line_entries:
        text = _normalize_text(line.text)
        match = _AFFILIATION_LINE_RE.match(text)
        if match:
            markers.add(match.group(1))
    return markers


def _has_attached_marker_mode(
    line_entries: Sequence[_LineEntry],
    affiliation_markers: set[str],
) -> bool:
    if not affiliation_markers:
        return False
    for line in line_entries:
        text = _normalize_text(line.text)
        if _is_stop_line(text):
            break
        if _ATTACHED_MARKER_TRAILER_RE.search(text):
            return True
        segments = _split_explicit_segments(_prepare_author_line(text))
        if _should_strip_terminal_affiliation_markers(
            segments,
            affiliation_markers,
            allow_terminal_affiliation_marker=True,
        ):
            return True
    return False


def _should_strip_terminal_affiliation_markers(
    segments: Sequence[str],
    affiliation_markers: set[str],
    *,
    allow_terminal_affiliation_marker: bool,
) -> bool:
    if not allow_terminal_affiliation_marker or not affiliation_markers or len(segments) < 2:
        return False

    endings: list[str] = []
    for segment in segments:
        cleaned = segment.strip(" ,;")
        if not cleaned:
            return False
        explicit = _ATTACHED_MARKER_TRAILER_RE.match(cleaned)
        if explicit:
            attached = explicit.group("attached")
            if attached not in affiliation_markers:
                return False
            endings.append(attached)
            continue
        last_token = cleaned.split()[-1].strip(" ,;")
        if len(last_token) < 3:
            return False
        ending = last_token[-1].lower()
        if ending not in affiliation_markers:
            return False
        endings.append(ending)
    return len(set(endings)) >= 2


def _strip_attached_marker_suffix(
    segment: str,
    *,
    affiliation_markers: set[str],
    allow_terminal_affiliation_marker: bool,
) -> tuple[str, list[str]]:
    explicit = _ATTACHED_MARKER_TRAILER_RE.match(segment)
    if explicit:
        base = explicit.group("base").strip(" ,;")
        attached = explicit.group("attached")
        trailer = explicit.group("trailer") or ""
        if (not affiliation_markers or attached in affiliation_markers) and _parse_single_author(base):
            return base, [attached, *_extract_attached_markers(trailer)]

    if allow_terminal_affiliation_marker and affiliation_markers:
        terminal = _TERMINAL_ATTACHED_MARKER_RE.match(segment)
        if terminal:
            base = terminal.group("base").strip(" ,;")
            attached = terminal.group("attached")
            if attached in affiliation_markers and _parse_single_author(base):
                return base, [attached]

    return segment, []


def _extract_attached_markers(value: str) -> list[str]:
    markers: list[str] = []
    for char in value:
        if char.islower() or _ATTACHED_MARKER_SYMBOLS_RE.fullmatch(char):
            markers.append(char)
    return markers


def _merge_marker_lists(left: Sequence[str], right: Sequence[str]) -> list[str]:
    merged: list[str] = []
    for marker in [*left, *right]:
        normalized = marker.strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def _candidate_confidence(base_confidence: float, markers: list[str], raw: str) -> float:
    confidence = base_confidence
    if markers:
        confidence += 0.02
    if len(raw.split()) >= 3:
        confidence += 0.01
    return min(confidence, 0.99)


def _bbox_key(bbox: Any) -> tuple[float, float]:
    if not bbox or len(bbox) < 2:
        return (10**9, 10**9)
    return float(bbox[1]), float(bbox[0])


def _merge_author_chunks(chunks: list[str]) -> list[str]:
    merged: list[str] = []
    for chunk in chunks:
        if merged and _looks_like_split_name(merged[-1], chunk):
            merged[-1] = f"{merged[-1]} {chunk.lstrip()}"
        else:
            merged.append(chunk)
    return merged


def _looks_like_split_name(previous: str, current: str) -> bool:
    previous_text = previous.rstrip()
    if not previous_text or previous_text.endswith((",", ";")):
        return False

    previous_token = previous_text.split()[-1].strip(" ,;")
    current_parts = current.lstrip().split(maxsplit=1)
    if not current_parts:
        return False
    current_token = current_parts[0].strip(" ,;")

    if not re.fullmatch(r"[A-Z][a-z]+", previous_token):
        return False
    if not re.fullmatch(r"[A-Z][A-Za-z'’`\-]*\d*(?:,\d+)*[\*\u2217\u2020\u2021\u00a7\u00b6xXB#]*", current_token):
        return False
    return True
