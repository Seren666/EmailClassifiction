from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pdf_extract import PDFExtractError, extract_pages, is_readable_text


PREFERRED_SAMPLE_IDS = [
    "S001",
    "S002",
    "S003",
    "S004",
    "S005",
    "S006",
    "S007",
    "S008",
    "S009",
    "S010",
]


def load_existing_samples(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    existing_rows: list[dict[str, str]] = []
    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if not sample_id or sample_id.startswith("SXXX"):
            continue
        pdf_path = Path(row["pdf_path"])
        if pdf_path.exists():
            existing_rows.append(row)
    return existing_rows


def choose_samples(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    by_id = {(row.get("sample_id") or "").strip(): row for row in rows}
    selected: list[dict[str, str]] = []
    seen: set[str] = set()

    for sample_id in PREFERRED_SAMPLE_IDS:
        row = by_id.get(sample_id)
        if row:
            selected.append(row)
            seen.add(sample_id)
            if len(selected) >= limit:
                return selected[:limit]

    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if sample_id in seen:
            continue
        selected.append(row)
        seen.add(sample_id)
        if len(selected) >= limit:
            break

    return selected[:limit]


def format_page_stats(sample_pages) -> tuple[str, str]:
    lengths = ", ".join(f"p{page.page_number}={len(page.text)}" for page in sample_pages)
    extractors = ", ".join(f"p{page.page_number}:{page.extractor_used}" for page in sample_pages)
    return lengths, extractors


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for Step 3 PDF text extraction.")
    parser.add_argument("--limit", type=int, default=12, help="Number of samples to smoke test.")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages to extract per PDF.")
    parser.add_argument(
        "--min-readable-chars",
        type=int,
        default=80,
        help="Threshold used by the simple readable-text heuristic.",
    )
    args = parser.parse_args()

    repo_root = REPO_ROOT
    csv_path = repo_root / "data" / "samples_v1.csv"
    all_rows = load_existing_samples(csv_path)
    selected_rows = choose_samples(all_rows, args.limit)

    print(f"[INFO] CSV source: {csv_path}")
    print(f"[INFO] Existing PDF samples found: {len(all_rows)}")
    print(f"[INFO] Smoke test sample count: {len(selected_rows)}")

    successes = 0
    failures: list[tuple[str, str]] = []

    for row in selected_rows:
        sample_id = (row.get("sample_id") or "").strip()
        pdf_path = repo_root / row["pdf_path"]
        try:
            pages = extract_pages(pdf_path, max_pages=args.max_pages)
            readable = any(is_readable_text(page.text, args.min_readable_chars) for page in pages)
            lengths, extractors = format_page_stats(pages)
            if readable:
                successes += 1
            else:
                failures.append((sample_id, "text extracted but below readable threshold"))
            print(
                f"[SAMPLE] {sample_id} | pdf_path={pdf_path} | pages={len(pages)} | "
                f"text_lengths={lengths} | extractors={extractors} | readable={readable}"
            )
            for page in pages:
                if page.error:
                    print(f"[WARN] {sample_id} page {page.page_number}: {page.error}")
        except (FileNotFoundError, PDFExtractError, ValueError) as exc:
            failures.append((sample_id, str(exc)))
            print(f"[ERROR] {sample_id} | pdf_path={pdf_path} | reason={exc}")
        except Exception as exc:
            failures.append((sample_id, f"unexpected_error: {exc}"))
            print(f"[ERROR] {sample_id} | pdf_path={pdf_path} | reason=unexpected_error: {exc}")

    print(f"[SUMMARY] total={len(selected_rows)} | success={successes} | failure={len(failures)}")
    if failures:
        print("[FAILED_SAMPLES]")
        for sample_id, reason in failures:
            print(f"- {sample_id}: {reason}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
