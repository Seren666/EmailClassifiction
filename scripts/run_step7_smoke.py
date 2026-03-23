from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from assemble_structured_output import assemble_structured_output_from_pdf


PREFERRED_SAMPLE_IDS = [
    "S001",
    "S002",
    "S004",
    "S006",
    "S007",
    "S008",
    "S009",
    "S010",
    "S026",
    "S027",
    "S028",
    "S029",
    "S030",
]
REQUIRED_KEYS = {
    "authors",
    "first_author",
    "co_first_authors",
    "equal_contribution_detected",
    "emails",
    "pairs",
    "shared_emails",
    "unmatched_authors",
    "unmatched_emails",
    "stats",
    "first_author_email",
    "first_author_region",
}
REQUIRED_STATS_KEYS = {
    "author_count",
    "email_count",
    "pair_count",
    "shared_email_count",
    "unmatched_author_count",
    "unmatched_email_count",
    "first_author_found",
    "has_first_author_email",
}


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def choose_samples(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    by_id = {(row.get("sample_id") or "").strip(): row for row in rows}
    selected: list[dict[str, str]] = []
    seen: set[str] = set()

    for sample_id in PREFERRED_SAMPLE_IDS:
        row = by_id.get(sample_id)
        if row and Path(REPO_ROOT / row["pdf_path"]).exists():
            selected.append(row)
            seen.add(sample_id)
            if len(selected) >= limit:
                return selected[:limit]

    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if not sample_id or sample_id.startswith("SXXX") or sample_id in seen:
            continue
        if not Path(REPO_ROOT / row["pdf_path"]).exists():
            continue
        selected.append(row)
        seen.add(sample_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def parse_json_field(row: dict[str, str], key: str, fallback: Any) -> Any:
    raw = row.get(key)
    if not raw or raw == "None":
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def validate_structure(result: dict[str, Any]) -> tuple[bool, str]:
    missing = sorted(REQUIRED_KEYS - set(result))
    if missing:
        return False, f"missing required keys: {missing}"

    stats = result.get("stats")
    if not isinstance(stats, dict):
        return False, "stats is not a dict"
    missing_stats = sorted(REQUIRED_STATS_KEYS - set(stats))
    if missing_stats:
        return False, f"missing stats keys: {missing_stats}"

    authors = result.get("authors") or []
    emails = result.get("emails") or []
    pairs = result.get("pairs") or []
    shared_emails = result.get("shared_emails") or []
    unmatched_authors = result.get("unmatched_authors") or []
    unmatched_emails = result.get("unmatched_emails") or []
    first_author = result.get("first_author")
    first_author_email = result.get("first_author_email")
    first_author_region = result.get("first_author_region")

    if stats["author_count"] != len(authors):
        return False, "author_count does not match authors length"
    if stats["email_count"] != len(emails):
        return False, "email_count does not match emails length"
    if stats["pair_count"] != len(pairs):
        return False, "pair_count does not match pairs length"
    if stats["shared_email_count"] != len(shared_emails):
        return False, "shared_email_count does not match shared_emails length"
    if stats["unmatched_author_count"] != len(unmatched_authors):
        return False, "unmatched_author_count does not match unmatched_authors length"
    if stats["unmatched_email_count"] != len(unmatched_emails):
        return False, "unmatched_email_count does not match unmatched_emails length"
    if stats["first_author_found"] != (first_author is not None):
        return False, "first_author_found is inconsistent with first_author"
    if stats["has_first_author_email"] != (first_author_email is not None):
        return False, "has_first_author_email is inconsistent with first_author_email"

    if authors:
        if first_author is None:
            return False, "authors exist but first_author is null"
        if first_author.get("author_norm") != authors[0].get("author_norm"):
            return False, "first_author is not the first author by order"
    elif first_author is not None:
        return False, "authors is empty but first_author is not null"

    pair_emails = {item.get("email") for item in pairs}
    pair_authors = {item.get("author_norm") for item in pairs}
    if first_author_email is not None:
        if first_author_email not in pair_emails:
            return False, "first_author_email is not drawn from confirmed pairs"
        if first_author is None or first_author.get("author_norm") not in pair_authors:
            return False, "first_author_email exists but first author has no confirmed pair"
        first_pair_emails = {
            item.get("email")
            for item in pairs
            if item.get("author_norm") == first_author.get("author_norm")
        }
        if first_author_email not in first_pair_emails:
            return False, "first_author_email does not belong to the first author's confirmed pair"
    elif first_author_region is not None:
        return False, "first_author_region should be null when first_author_email is null"

    return True, "structure is internally consistent"


def evaluate_against_ground_truth(
    result: dict[str, Any],
    row: dict[str, str],
) -> tuple[bool, str]:
    structural_ok, structural_reason = validate_structure(result)
    if not structural_ok:
        return False, structural_reason

    annotation_status = (row.get("annotation_status") or "").strip().lower()
    gt_first_author = parse_json_field(row, "ground_truth_first_author_json", None)
    gt_pairs = parse_json_field(row, "ground_truth_pairs_json", [])

    first_author = result.get("first_author")
    if gt_first_author:
        gt_first_author_norm = gt_first_author.get("author_norm")
        if first_author is None:
            return False, "ground truth has first author but result first_author is null"
        if first_author.get("author_norm") != gt_first_author_norm:
            return False, f"first_author mismatch: predicted={first_author.get('author_norm')} expected={gt_first_author_norm}"

    first_author_email = result.get("first_author_email")
    gt_first_author_norm = gt_first_author.get("author_norm") if gt_first_author else None
    gt_first_pairs = [
        item
        for item in gt_pairs
        if item.get("author_norm") == gt_first_author_norm and item.get("email")
    ]
    gt_first_emails = {item["email"].lower() for item in gt_first_pairs}

    if annotation_status == "done":
        if gt_first_emails:
            if first_author_email is None:
                return False, "ground truth has a first-author email but result kept null"
            if first_author_email.lower() not in gt_first_emails:
                return False, f"first_author_email mismatch: predicted={first_author_email} expected one of={sorted(gt_first_emails)}"
            gt_regions = {
                item.get("region")
                for item in gt_first_pairs
                if item.get("email", "").lower() == first_author_email.lower() and item.get("region")
            }
            if gt_regions and result.get("first_author_region") not in gt_regions:
                return False, f"first_author_region mismatch: predicted={result.get('first_author_region')} expected one of={sorted(gt_regions)}"
        elif first_author_email is not None:
            return False, "ground truth has no first-author email but result produced one"
    else:
        if gt_first_emails and first_author_email is not None and first_author_email.lower() not in gt_first_emails:
            return False, f"needs_review sample produced contradictory first_author_email={first_author_email}"

    return True, structural_reason


def compact_showcase(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "first_author": result.get("first_author"),
        "first_author_email": result.get("first_author_email"),
        "first_author_region": result.get("first_author_region"),
        "pairs": result.get("pairs", [])[:5],
        "shared_emails": result.get("shared_emails", []),
        "stats": result.get("stats"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for Step 7 structured output assembly.")
    parser.add_argument("--limit", type=int, default=12, help="Number of PDFs to smoke test.")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages to inspect per PDF.")
    parser.add_argument("--show-samples", type=int, default=4, help="Number of result samples to showcase.")
    parser.add_argument("--seed", type=int, default=41, help="Random seed for showcase sampling.")
    args = parser.parse_args()

    csv_path = REPO_ROOT / "data" / "samples_v1.csv"
    rows = load_rows(csv_path)
    selected_rows = choose_samples(rows, args.limit)

    print(f"[INFO] CSV source: {csv_path}")
    print(f"[INFO] Smoke test sample count: {len(selected_rows)}")

    success_count = 0
    failures: list[tuple[str, str]] = []
    showcase_pool: list[tuple[str, str, dict[str, Any], str]] = []

    for row in selected_rows:
        sample_id = (row.get("sample_id") or "").strip()
        pdf_path = REPO_ROOT / row["pdf_path"]
        try:
            result = assemble_structured_output_from_pdf(pdf_path, max_pages=args.max_pages)
            usable, reason = evaluate_against_ground_truth(result, row)
            if usable:
                success_count += 1
            else:
                failures.append((sample_id, reason))

            print(
                f"[SAMPLE] {sample_id} | first_author={_safe_norm(result.get('first_author'))} | "
                f"first_author_email={result.get('first_author_email')} | "
                f"first_author_region={result.get('first_author_region')} | "
                f"pair_count={result['stats']['pair_count']} | "
                f"unmatched_author_count={result['stats']['unmatched_author_count']} | "
                f"unmatched_email_count={result['stats']['unmatched_email_count']} | usable={usable}"
            )
            print(f"[EVAL] {sample_id} | reason={reason}")
            showcase_pool.append((sample_id, str(pdf_path), compact_showcase(result), reason))
        except Exception as exc:
            failures.append((sample_id, str(exc)))
            print(f"[ERROR] {sample_id} | pdf_path={pdf_path} | reason={exc}")

    print(f"[SUMMARY] total={len(selected_rows)} | success={success_count} | failure={len(failures)}")
    if failures:
        print("[FAILED_SAMPLES]")
        for sample_id, reason in failures:
            print(f"- {sample_id}: {reason}")

    if showcase_pool:
        sample_count = min(args.show_samples, len(showcase_pool))
        chosen = random.Random(args.seed).sample(showcase_pool, sample_count)
        print("[SHOWCASE]")
        for sample_id, pdf_path, payload, reason in chosen:
            print(f"- {sample_id} | pdf_path={pdf_path} | note={reason}")
            print(json.dumps(payload, ensure_ascii=False))

    return 0


def _safe_norm(first_author: Any) -> str | None:
    if isinstance(first_author, dict):
        return first_author.get("author_norm")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
