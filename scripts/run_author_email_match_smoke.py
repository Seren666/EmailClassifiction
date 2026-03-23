from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from author_email_match import match_authors_and_emails_from_pdf
from author_extract import extract_authors_from_pdf
from email_extract import extract_emails_from_pdf


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


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


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


def parse_ground_truth_pairs(row: dict[str, str]) -> set[tuple[str, str]]:
    raw = row.get("ground_truth_pairs_json") or "[]"
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    pairs: set[tuple[str, str]] = set()
    for item in items:
        author = (item.get("author_norm") or "").strip()
        email = (item.get("email") or "").strip().lower()
        if author and email:
            pairs.add((author, email))
    return pairs


def evaluate_usable(
    predicted_pairs: set[tuple[str, str]],
    ground_truth_pairs: set[tuple[str, str]],
    annotation_status: str,
) -> tuple[bool, str, int, int]:
    overlap = predicted_pairs & ground_truth_pairs
    extra = predicted_pairs - ground_truth_pairs
    status = annotation_status.strip().lower()

    if not predicted_pairs:
        return False, "no author-email pairs extracted", len(overlap), len(extra)

    if status == "done":
        if extra:
            return False, f"false positive pairs detected: {sorted(extra)}", len(overlap), len(extra)
        if not overlap:
            return False, "no overlap with ground truth pairs", len(overlap), len(extra)
        return True, f"predicted pairs are a conservative subset of ground truth ({len(overlap)} overlap)", len(overlap), len(extra)

    if ground_truth_pairs:
        if overlap:
            note = f"needs_review sample; overlap={len(overlap)}"
            if extra:
                note += f"; extra_unverified={len(extra)}"
            return True, note, len(overlap), len(extra)
        return False, "needs_review sample but no overlap with available ground truth pairs", len(overlap), len(extra)

    return True, "needs_review sample with non-empty pairs and no fixed ground truth pairs", len(overlap), len(extra)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for Step 6 author-email matching.")
    parser.add_argument("--limit", type=int, default=12, help="Number of PDFs to smoke test.")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages to inspect per PDF.")
    parser.add_argument("--show-samples", type=int, default=4, help="Number of matched samples to showcase.")
    parser.add_argument("--seed", type=int, default=29, help="Random seed for showcase sampling.")
    args = parser.parse_args()

    csv_path = REPO_ROOT / "data" / "samples_v1.csv"
    rows = load_rows(csv_path)
    selected_rows = choose_samples(rows, args.limit)

    print(f"[INFO] CSV source: {csv_path}")
    print(f"[INFO] Smoke test sample count: {len(selected_rows)}")

    success_count = 0
    failures: list[tuple[str, str]] = []
    showcase_pool: list[tuple[str, str, list[tuple[str, str, str]], str]] = []

    for row in selected_rows:
        sample_id = (row.get("sample_id") or "").strip()
        pdf_path = REPO_ROOT / row["pdf_path"]
        annotation_status = row.get("annotation_status") or ""
        ground_truth_pairs = parse_ground_truth_pairs(row)
        try:
            authors = extract_authors_from_pdf(pdf_path, max_pages=args.max_pages)
            emails = extract_emails_from_pdf(pdf_path, max_pages=args.max_pages)
            pairs = match_authors_and_emails_from_pdf(pdf_path, max_pages=args.max_pages)
            pair_triplets = [
                (pair.author_normalized, pair.email_normalized, pair.match_reason)
                for pair in pairs
            ]
            predicted_set = {(pair.author_normalized, pair.email_normalized) for pair in pairs}
            usable, reason, overlap_count, extra_count = evaluate_usable(
                predicted_set,
                ground_truth_pairs,
                annotation_status,
            )
            if usable:
                success_count += 1
            else:
                failures.append((sample_id, reason))

            print(
                f"[SAMPLE] {sample_id} | pdf_path={pdf_path} | authors={len(authors)} | "
                f"emails={len(emails)} | pairs={len(pairs)} | usable={usable} | pair_list={pair_triplets}"
            )
            print(
                f"[EVAL] {sample_id} | annotation_status={annotation_status} | "
                f"overlap={overlap_count} | extra={extra_count} | reason={reason}"
            )
            showcase_pool.append((sample_id, str(pdf_path), pair_triplets, reason))
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
        rng = random.Random(args.seed)
        chosen = rng.sample(showcase_pool, sample_count)
        print("[SHOWCASE]")
        for sample_id, pdf_path, pair_triplets, reason in chosen:
            print(f"- {sample_id} | pdf_path={pdf_path} | pairs={pair_triplets} | note={reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
