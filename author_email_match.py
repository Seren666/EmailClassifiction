from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from author_extract import AuthorCandidate, extract_authors_from_pages
from email_extract import EmailCandidate, extract_emails_from_pages
from pdf_extract import PageText, extract_pages


DEFAULT_MAX_PAGES = 2
MIN_ACCEPTED_SCORE = 0.82
MIN_SCORE_MARGIN = 0.08
VOWELS = set("aeiou")
PINYIN_INITIALS = [
    "zh",
    "ch",
    "sh",
    "b",
    "p",
    "m",
    "f",
    "d",
    "t",
    "n",
    "l",
    "g",
    "k",
    "h",
    "j",
    "q",
    "x",
    "r",
    "z",
    "c",
    "s",
    "y",
    "w",
]
CORRESPONDENCE_HINTS = ("correspond", "correspondence")
MARKER_HINT_RE = re.compile(r"[\*\u2217\u2020\u2021\u00a7\u00b6#xXB]")
LOCAL_PART_SPLIT_RE = re.compile(r"[._+\-]+")


@dataclass
class AuthorEmailPair:
    author_raw: str
    author_normalized: str
    email_raw: str
    email_normalized: str
    match_reason: str
    confidence: float
    page_number: int | None
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class _AuthorProfile:
    candidate: AuthorCandidate
    normalized_ascii: str
    tokens: list[str]
    given_tokens: list[str]
    surname: str
    first_given: str
    given_concat: str
    compact: str
    given_initials: str
    all_initials: str
    compressed_given_initials: str
    line_index: int | None
    page_order: int


@dataclass
class _EmailProfile:
    candidate: EmailCandidate
    local_part: str
    local_letters: str
    local_tokens: list[str]
    has_correspondence_hint: bool
    marker_hints: list[str]
    is_grouped: bool
    line_index: int | None
    page_order: int
    group_position: int


@dataclass
class _RuleMatch:
    rule: str
    score: float
    category: str
    note: str


@dataclass
class _PairEvidence:
    author_index: int
    email_index: int
    match_reason: str
    confidence: float
    notes: list[str]


def match_authors_and_emails(
    authors: Sequence[AuthorCandidate] | Iterable[AuthorCandidate],
    emails: Sequence[EmailCandidate] | Iterable[EmailCandidate],
    pages: Sequence[PageText] | None = None,
) -> list[AuthorEmailPair]:
    author_list = list(authors)
    email_list = list(emails)
    if not author_list or not email_list:
        return []

    page_lookup = _build_page_lookup(pages or [])
    author_profiles = _build_author_profiles(author_list, page_lookup)
    email_profiles = _build_email_profiles(email_list, page_lookup)

    proposals: list[_PairEvidence] = []
    for email_index, email_profile in enumerate(email_profiles):
        candidates: list[_PairEvidence] = []
        for author_index, author_profile in enumerate(author_profiles):
            evidence = _score_pair(
                author_index=author_index,
                author_profile=author_profile,
                email_index=email_index,
                email_profile=email_profile,
                authors_on_page=author_profiles,
                emails_on_page=email_profiles,
            )
            if evidence is not None:
                candidates.append(evidence)
        best = _choose_best_candidate(candidates)
        if best is not None:
            proposals.append(best)

    final_pairs = _finalize_pairs(proposals, author_profiles, email_profiles)
    return [
        AuthorEmailPair(
            author_raw=author_profiles[item.author_index].candidate.raw,
            author_normalized=author_profiles[item.author_index].candidate.normalized,
            email_raw=email_profiles[item.email_index].candidate.raw,
            email_normalized=email_profiles[item.email_index].candidate.normalized,
            match_reason=item.match_reason,
            confidence=item.confidence,
            page_number=email_profiles[item.email_index].candidate.page_number,
            notes="; ".join(item.notes),
        )
        for item in final_pairs
    ]


def match_authors_and_emails_from_pdf(
    pdf_path: str | Path,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[AuthorEmailPair]:
    pages = extract_pages(pdf_path, max_pages=max_pages)
    authors = extract_authors_from_pages(pages)
    emails = extract_emails_from_pages(pages)
    return match_authors_and_emails(authors, emails, pages=pages)


def _build_page_lookup(pages: Sequence[PageText]) -> dict[int, list[str]]:
    lookup: dict[int, list[str]] = {}
    for page in pages:
        if page.lines:
            ordered = sorted(
                page.lines,
                key=lambda item: (
                    item.get("bbox", [10**9, 10**9])[1] if item.get("bbox") else 10**9,
                    item.get("bbox", [10**9, 10**9])[0] if item.get("bbox") else 10**9,
                    item.get("block_index", 10**9),
                    item.get("line_index", 10**9),
                ),
            )
            lookup[page.page_number] = [str(item.get("text") or "") for item in ordered]
            continue
        lookup[page.page_number] = page.text.splitlines()
    return lookup


def _build_author_profiles(
    authors: Sequence[AuthorCandidate],
    page_lookup: dict[int, list[str]],
) -> list[_AuthorProfile]:
    profiles: list[_AuthorProfile] = []
    for page_order, author in enumerate(authors):
        normalized_ascii = _to_ascii(author.normalized)
        tokens = [token for token in re.findall(r"[a-z]+", normalized_ascii) if token]
        given_tokens = tokens[:-1]
        surname = tokens[-1] if tokens else ""
        first_given = given_tokens[0] if given_tokens else ""
        given_concat = "".join(given_tokens)
        compact = "".join(tokens)
        given_initials = "".join(token[0] for token in given_tokens if token)
        all_initials = "".join(token[0] for token in tokens if token)
        compressed_given = "".join(_compressed_initials(token) for token in given_tokens if token)
        line_index = _locate_line_index(
            page_lookup.get(author.page_number or -1, []),
            [author.raw, author.normalized, author.source_snippet],
        )
        profiles.append(
            _AuthorProfile(
                candidate=author,
                normalized_ascii=normalized_ascii,
                tokens=tokens,
                given_tokens=given_tokens,
                surname=surname,
                first_given=first_given,
                given_concat=given_concat,
                compact=compact,
                given_initials=given_initials,
                all_initials=all_initials,
                compressed_given_initials=compressed_given,
                line_index=line_index,
                page_order=page_order,
            )
        )
    return profiles


def _build_email_profiles(
    emails: Sequence[EmailCandidate],
    page_lookup: dict[int, list[str]],
) -> list[_EmailProfile]:
    unsorted_profiles: list[_EmailProfile] = []
    for email in emails:
        local_part = email.normalized.partition("@")[0]
        local_letters = re.sub(r"[^a-z]", "", local_part.lower())
        local_tokens = [
            re.sub(r"[^a-z]", "", token.lower())
            for token in LOCAL_PART_SPLIT_RE.split(local_part)
            if re.sub(r"[^a-z]", "", token.lower())
        ]
        snippet_ascii = _to_ascii(email.source_snippet)
        is_grouped = email.pattern_type.startswith("grouped_")
        line_index = _locate_line_index(
            page_lookup.get(email.page_number or -1, []),
            [email.raw, email.source_snippet] if is_grouped else [email.raw, email.normalized, local_part, email.source_snippet],
        )
        group_position = _group_position(email)
        unsorted_profiles.append(
            _EmailProfile(
                candidate=email,
                local_part=local_part,
                local_letters=local_letters,
                local_tokens=local_tokens,
                has_correspondence_hint=any(hint in snippet_ascii for hint in CORRESPONDENCE_HINTS),
                marker_hints=_extract_marker_hints(email.source_snippet),
                is_grouped=is_grouped,
                line_index=line_index,
                page_order=0,
                group_position=group_position,
            )
        )

    sorted_profiles = sorted(
        unsorted_profiles,
        key=lambda item: (
            item.candidate.page_number if item.candidate.page_number is not None else 10**9,
            item.line_index if item.line_index is not None else 10**9,
            item.group_position if item.group_position >= 0 else 10**9,
            item.candidate.normalized,
        ),
    )
    profiles: list[_EmailProfile] = []
    for page_order, profile in enumerate(sorted_profiles):
        profile.page_order = page_order
        profiles.append(profile)
    return profiles


def _score_pair(
    author_index: int,
    author_profile: _AuthorProfile,
    email_index: int,
    email_profile: _EmailProfile,
    authors_on_page: Sequence[_AuthorProfile],
    emails_on_page: Sequence[_EmailProfile],
) -> _PairEvidence | None:
    if (
        author_profile.candidate.page_number is not None
        and email_profile.candidate.page_number is not None
        and author_profile.candidate.page_number != email_profile.candidate.page_number
    ):
        return None

    lexical = _match_local_part(author_profile, email_profile)
    if email_profile.is_grouped and lexical is None:
        return None
    marker_bonus, marker_note = _marker_support(author_profile, email_profile, authors_on_page)
    proximity_bonus, proximity_note = _proximity_support(author_profile, email_profile, authors_on_page, emails_on_page)
    order_bonus, order_note = _order_support(author_profile, email_profile)

    if lexical is None and marker_bonus == 0 and proximity_bonus == 0:
        return None

    notes: list[str] = []
    confidence = 0.0
    match_reason = ""
    if lexical is not None:
        confidence = lexical.score
        match_reason = lexical.rule
        notes.append(lexical.note)
    else:
        confidence = 0.56
        match_reason = "marker_supported_match"

    if marker_bonus:
        confidence += marker_bonus
        notes.append(marker_note)
    if proximity_bonus:
        confidence += proximity_bonus
        notes.append(proximity_note)
    if order_bonus:
        confidence += order_bonus
        notes.append(order_note)

    confidence = min(confidence, 0.99)

    if lexical is not None and lexical.category == "weak" and proximity_bonus >= 0.14:
        match_reason = "proximity_supported_match"
    elif lexical is not None and email_profile.is_grouped:
        match_reason = "grouped_email_expansion_match"
    elif lexical is None and proximity_bonus >= 0.28:
        match_reason = "proximity_supported_match"
    elif lexical is None and marker_bonus >= 0.24:
        match_reason = "marker_supported_match"

    if lexical is None and confidence < MIN_ACCEPTED_SCORE:
        return None
    if lexical is not None and lexical.category == "weak" and confidence < 0.84:
        return None
    if lexical is not None and lexical.category == "abbrev" and confidence < 0.82:
        return None
    if lexical is not None and lexical.category == "strong" and confidence < 0.82:
        return None

    return _PairEvidence(
        author_index=author_index,
        email_index=email_index,
        match_reason=match_reason,
        confidence=round(confidence, 3),
        notes=[note for note in notes if note],
    )


def _match_local_part(author: _AuthorProfile, email: _EmailProfile) -> _RuleMatch | None:
    local = email.local_letters
    if not local or not author.tokens:
        return None

    token_combo = _tokenized_combo_match(author, email)
    if token_combo is not None:
        return token_combo

    direct_variants = _direct_variants(author)
    if local in direct_variants:
        return _RuleMatch(
            rule="exact_localpart_match",
            score=0.96,
            category="strong",
            note=f"local_part={local} matched direct variant",
        )

    prefix_variants = _prefix_variants(author)
    if local in prefix_variants:
        return _RuleMatch(
            rule="exact_localpart_match",
            score=0.92,
            category="strong",
            note=f"local_part={local} matched name prefix variant",
        )

    abbrev_variants = _abbreviation_variants(author)
    if local in abbrev_variants:
        return _RuleMatch(
            rule="initials_plus_surname_match",
            score=0.87,
            category="abbrev",
            note=f"local_part={local} matched abbreviation variant",
        )

    token_match = _token_match(author, email)
    if token_match is not None:
        return token_match

    weak_match = _weak_prefix_match(author, email)
    if weak_match is not None:
        return weak_match

    return None


def _direct_variants(author: _AuthorProfile) -> set[str]:
    variants: set[str] = set()
    if author.surname and len(author.surname) >= 6:
        variants.add(author.surname)
    if author.first_given and author.surname:
        variants.add(author.first_given + author.surname)
        variants.add(author.surname + author.first_given)
    if author.given_concat and author.surname:
        variants.add(author.given_concat + author.surname)
        variants.add(author.surname + author.given_concat)
    if author.compact:
        variants.add(author.compact)
    return {item for item in variants if item}


def _prefix_variants(author: _AuthorProfile) -> set[str]:
    variants: set[str] = set()
    if not author.first_given:
        return variants
    for length in range(2, min(len(author.first_given), 5) + 1):
        prefix = author.first_given[:length]
        if author.surname:
            variants.add(prefix + author.surname)
            variants.add(author.surname + prefix)
    return variants


def _abbreviation_variants(author: _AuthorProfile) -> set[str]:
    variants: set[str] = set()
    if author.given_initials and author.surname:
        variants.add(author.given_initials + author.surname)
        variants.add(author.surname + author.given_initials)
        variants.add(author.given_initials + author.surname[0])
        variants.add(author.surname[0] + author.given_initials)
    if author.all_initials:
        variants.add(author.all_initials)
    if author.first_given and author.surname:
        variants.add(author.first_given[:1] + author.surname)
        variants.add(author.surname + author.first_given[:1])
        for length in range(2, min(len(author.first_given), 5) + 1):
            prefix = author.first_given[:length]
            variants.add(prefix + author.surname[0])
            variants.add(author.surname[0] + prefix)
    if author.compressed_given_initials and author.surname:
        variants.add(author.surname + author.compressed_given_initials)
        variants.add(author.surname[0] + author.compressed_given_initials)
        variants.add(author.compressed_given_initials + author.surname)
        variants.add(author.compressed_given_initials + author.surname[0])
    return {item for item in variants if item}


def _token_match(author: _AuthorProfile, email: _EmailProfile) -> _RuleMatch | None:
    local = email.local_letters
    token_set = {token for token in author.tokens if len(token) >= 4}
    if local in token_set:
        return _RuleMatch(
            rule="exact_localpart_match",
            score=0.88,
            category="strong",
            note=f"local_part={local} matched a unique name token candidate",
        )
    return None


def _tokenized_combo_match(author: _AuthorProfile, email: _EmailProfile) -> _RuleMatch | None:
    if len(email.local_tokens) < 2 or not author.surname:
        return None
    token_set = set(email.local_tokens)
    surname_token = author.surname
    combo_tokens = {
        author.given_initials,
        author.compressed_given_initials,
        author.surname[0] + author.given_initials if author.given_initials else "",
        author.surname[0] + author.compressed_given_initials if author.compressed_given_initials else "",
        author.first_given[:1] if author.first_given else "",
    }
    combo_tokens = {token for token in combo_tokens if token}
    if surname_token in token_set and any(token in token_set for token in combo_tokens):
        return _RuleMatch(
            rule="initials_plus_surname_match",
            score=0.9,
            category="abbrev",
            note=f"local tokens={email.local_tokens} matched surname+abbreviation pattern",
        )
    return None


def _weak_prefix_match(author: _AuthorProfile, email: _EmailProfile) -> _RuleMatch | None:
    local = email.local_letters
    if not local:
        return None
    strong_like_variants = _direct_variants(author) | _prefix_variants(author) | _abbreviation_variants(author)
    if len(author.first_given) >= 4:
        strong_like_variants.add(author.first_given)
    for variant in strong_like_variants:
        if len(variant) < 4:
            continue
        if local.startswith(variant) and 0 < len(local) - len(variant) <= 2:
            rule = "initials_plus_surname_match" if variant in _abbreviation_variants(author) else "exact_localpart_match"
            category = "abbrev" if rule == "initials_plus_surname_match" else "strong"
            score = 0.83 if category == "abbrev" else 0.82
            return _RuleMatch(
                rule=rule,
                score=score,
                category=category,
                note=f"local_part={local} extended variant={variant} with short suffix",
            )
    candidates: list[str] = []
    if author.first_given:
        candidates.append(author.first_given)
    candidates.extend(token for token in author.tokens if len(token) >= 4)
    for token in candidates:
        if len(token) < 4:
            continue
        if local.startswith(token[:4]) or token.startswith(local):
            return _RuleMatch(
                rule="proximity_supported_match",
                score=0.64,
                category="weak",
                note=f"local_part={local} weakly aligned with token prefix={token[:4]}",
            )
    return None


def _marker_support(
    author: _AuthorProfile,
    email: _EmailProfile,
    authors: Sequence[_AuthorProfile],
) -> tuple[float, str]:
    if not email.has_correspondence_hint:
        return 0.0, ""

    if "*" in author.candidate.markers:
        starred_authors = [item for item in authors if "*" in item.candidate.markers]
        if len(starred_authors) == 1:
            return 0.24, "unique '*' marker under correspondence hint"
        return 0.08, "shared '*' marker under correspondence hint"

    if any(marker in {"†", "‡", "#", "B"} for marker in author.candidate.markers):
        return 0.05, "non-star correspondence-style marker present under correspondence hint"
    return 0.0, ""


def _proximity_support(
    author: _AuthorProfile,
    email: _EmailProfile,
    authors: Sequence[_AuthorProfile],
    emails: Sequence[_EmailProfile],
) -> tuple[float, str]:
    if author.candidate.page_number != email.candidate.page_number:
        return 0.0, ""
    if author.line_index is None or email.line_index is None:
        return 0.0, ""

    distance = email.line_index - author.line_index
    if distance == 1:
        return 0.28, "email line immediately follows author line"
    if distance == 2:
        return 0.12, "email line is within two lines after author line"
    if abs(distance) <= 3:
        return 0.06, "author/email lines are nearby on the same page"
    return 0.0, ""


def _order_support(author: _AuthorProfile, email: _EmailProfile) -> tuple[float, str]:
    if author.candidate.page_number != email.candidate.page_number:
        return 0.0, ""
    if author.page_order == email.page_order:
        return 0.08, "author order matches email order on page"
    if abs(author.page_order - email.page_order) == 1:
        return 0.03, "author order is adjacent to email order on page"
    return 0.0, ""


def _choose_best_candidate(candidates: Sequence[_PairEvidence]) -> _PairEvidence | None:
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda item: item.confidence, reverse=True)
    best = ranked[0]
    if best.confidence < MIN_ACCEPTED_SCORE:
        return None
    if len(ranked) > 1 and ranked[1].confidence >= best.confidence - MIN_SCORE_MARGIN:
        return None
    return best


def _finalize_pairs(
    proposals: Sequence[_PairEvidence],
    authors: Sequence[_AuthorProfile],
    emails: Sequence[_EmailProfile],
) -> list[_PairEvidence]:
    by_author: dict[int, _PairEvidence] = {}
    for item in sorted(proposals, key=lambda entry: entry.confidence, reverse=True):
        current = by_author.get(item.author_index)
        if current is None:
            by_author[item.author_index] = item
            continue
        if item.confidence > current.confidence:
            by_author[item.author_index] = item

    used_emails: set[int] = set()
    final_pairs: list[_PairEvidence] = []
    for item in sorted(by_author.values(), key=lambda entry: authors[entry.author_index].candidate.author_index or 10**9):
        if item.email_index in used_emails:
            continue
        used_emails.add(item.email_index)
        final_pairs.append(item)
    return final_pairs


def _locate_line_index(lines: Sequence[str], candidates: Sequence[str]) -> int | None:
    normalized_lines = [_to_ascii(line) for line in lines]
    normalized_candidates = [candidate for candidate in (_to_ascii(item) for item in candidates) if candidate]
    for candidate in normalized_candidates:
        for index, line in enumerate(normalized_lines):
            if candidate and candidate in line:
                return index
    return None


def _extract_marker_hints(text: str) -> list[str]:
    normalized = text.replace("\u2217", "*")
    return MARKER_HINT_RE.findall(normalized)


def _group_position(email: EmailCandidate) -> int:
    local_part = email.normalized.partition("@")[0].lower()
    raw_lower = email.raw.lower()
    if local_part and local_part in raw_lower:
        return raw_lower.find(local_part)
    return -1


def _compressed_initials(token: str) -> str:
    letters = re.sub(r"[^a-z]", "", token.lower())
    if not letters:
        return ""
    initials = [letters[0]]
    vowel_positions = [index for index, char in enumerate(letters) if char in VOWELS]
    for current, next_vowel in zip(vowel_positions, vowel_positions[1:]):
        cluster = letters[current + 1:next_vowel]
        candidate = _rightmost_pinyin_initial(cluster)
        if candidate and candidate != initials[-1]:
            initials.append(candidate)
    return "".join(initials)


def _rightmost_pinyin_initial(cluster: str) -> str:
    best_char = ""
    best_position = -1
    for index in range(len(cluster)):
        remainder = cluster[index:]
        for initial in PINYIN_INITIALS:
            if remainder.startswith(initial) and index >= best_position:
                best_char = initial[0]
                best_position = index
                break
    return best_char


def _to_ascii(value: str) -> str:
    lowered = value.lower().replace("\u2217", "*")
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"\s+", " ", ascii_text)
    return ascii_text.strip()
