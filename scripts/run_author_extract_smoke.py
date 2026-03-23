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

from author_extract import extract_authors_from_pdf


PREFERRED_SAMPLE_IDS = [
    "S001",
    "S002",
    "S003",
    "S005",
    "S006",
    "S007",
    "S009",
    "S010",
    "S012",
    "S026",
    "S027",
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


def parse_ground_truth_authors(row: dict[str, str]) -> list[str]:
    raw = row.get("ground_truth_authors_json") or "[]"
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    authors: list[str] = []
    for item in items:
        normalized = (item.get("author_norm") or "").strip()
        if normalized:
            authors.append(normalized)
    return authors


def ordered_overlap(predicted: list[str], ground_truth: list[str]) -> int:
    gt_index = 0
    matched = 0
    for name in predicted:
        while gt_index < len(ground_truth) and ground_truth[gt_index] != name:
            gt_index += 1
        if gt_index >= len(ground_truth):
            break
        matched += 1
        gt_index += 1
    return matched


def minimum_required_matches(ground_truth_count: int) -> int:
    if ground_truth_count <= 1:
        return 1
    if ground_truth_count <= 5:
        return 2
    return 3


def evaluate_usable(predicted: list[str], ground_truth: list[str]) -> tuple[bool, str, int]:
    if not predicted:
        return False, "no authors extracted", 0
    if not ground_truth:
        return True, "no ground truth available; non-empty author list", len(predicted)

    first_author_ok = predicted[0] == ground_truth[0]
    overlap = ordered_overlap(predicted, ground_truth)
    required = minimum_required_matches(len(ground_truth))
    if not first_author_ok:
        return False, f"first author mismatch: predicted={predicted[0]!r} expected={ground_truth[0]!r}", overlap
    if overlap < required:
        return False, f"ordered overlap too low: {overlap} < {required}", overlap
    return True, f"first author ok; ordered overlap={overlap}", overlap


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for Step 5 author extraction.")
    parser.add_argument("--limit", type=int, default=12, help="Number of PDFs to smoke test.")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages to inspect per PDF.")
    parser.add_argument("--show-samples", type=int, default=4, help="Number of extracted samples to showcase.")
    parser.add_argument("--seed", type=int, default=23, help="Random seed for showcase sampling.")
    args = parser.parse_args()

    csv_path = REPO_ROOT / "data" / "samples_v1.csv"
    rows = load_rows(csv_path)
    selected_rows = choose_samples(rows, args.limit)

    print(f"[INFO] CSV source: {csv_path}")
    print(f"[INFO] Smoke test sample count: {len(selected_rows)}")

    usable_count = 0
    failures: list[tuple[str, str]] = []
    showcase_pool: list[tuple[str, str, list[str], bool, str]] = []

    for row in selected_rows:
        sample_id = (row.get("sample_id") or "").strip()
        pdf_path = REPO_ROOT / row["pdf_path"]
        ground_truth = parse_ground_truth_authors(row)
        try:
            authors = extract_authors_from_pdf(pdf_path, max_pages=args.max_pages)
            predicted = [author.normalized for author in authors]
            has_markers = any(author.markers for author in authors)
            usable, reason, overlap = evaluate_usable(predicted, ground_truth)
            if usable:
                usable_count += 1
            else:
                failures.append((sample_id, reason))

            print(
                f"[SAMPLE] {sample_id} | pdf_path={pdf_path} | count={len(authors)} | "
                f"markers_detected={has_markers} | usable={usable} | authors={predicted}"
            )
            print(
                f"[EVAL] {sample_id} | ordered_overlap={overlap} | ground_truth_count={len(ground_truth)} | "
                f"reason={reason}"
            )
            showcase_pool.append((sample_id, str(pdf_path), predicted, has_markers, reason))
        except Exception as exc:
            failures.append((sample_id, str(exc)))
            print(f"[ERROR] {sample_id} | pdf_path={pdf_path} | reason={exc}")

    print(f"[SUMMARY] total={len(selected_rows)} | success={usable_count} | failure={len(failures)}")
    if failures:
        print("[FAILED_SAMPLES]")
        for sample_id, reason in failures:
            print(f"- {sample_id}: {reason}")

    if showcase_pool:
        sample_count = min(args.show_samples, len(showcase_pool))
        rng = random.Random(args.seed)
        chosen = rng.sample(showcase_pool, sample_count)
        print("[SHOWCASE]")
        for sample_id, pdf_path, authors, has_markers, reason in chosen:
            print(
                f"- {sample_id} | pdf_path={pdf_path} | markers_detected={has_markers} | "
                f"authors={authors} | note={reason}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
