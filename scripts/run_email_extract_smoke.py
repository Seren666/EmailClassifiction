from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from email_extract import extract_emails_from_pdf


PREFERRED_SAMPLE_IDS = [
    'S001',
    'S003',
    'S005',
    'S006',
    'S007',
    'S009',
    'S010',
    'S014',
    'S017',
    'S019',
    'S020',
    'S021',
    'S022',
    'S027',
    'S030',
]


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def choose_samples(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    by_id = {(row.get('sample_id') or '').strip(): row for row in rows}
    selected: list[dict[str, str]] = []
    seen: set[str] = set()

    for sample_id in PREFERRED_SAMPLE_IDS:
        row = by_id.get(sample_id)
        if row and Path(REPO_ROOT / row['pdf_path']).exists():
            selected.append(row)
            seen.add(sample_id)
            if len(selected) >= limit:
                return selected[:limit]

    for row in rows:
        sample_id = (row.get('sample_id') or '').strip()
        if not sample_id or sample_id.startswith('SXXX') or sample_id in seen:
            continue
        if not Path(REPO_ROOT / row['pdf_path']).exists():
            continue
        selected.append(row)
        seen.add(sample_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def parse_ground_truth(row: dict[str, str]) -> set[str]:
    raw = row.get('ground_truth_emails_json') or '[]'
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    results: set[str] = set()
    for item in items:
        email = (item.get('email') or '').strip().lower()
        if email:
            results.add(email)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke test for Step 4 email extraction.')
    parser.add_argument('--limit', type=int, default=15, help='Number of PDFs to smoke test.')
    parser.add_argument('--max-pages', type=int, default=2, help='Maximum pages to inspect per PDF.')
    args = parser.parse_args()

    csv_path = REPO_ROOT / 'data' / 'samples_v1.csv'
    rows = load_rows(csv_path)
    selected_rows = choose_samples(rows, args.limit)

    print(f'[INFO] CSV source: {csv_path}')
    print(f'[INFO] Smoke test sample count: {len(selected_rows)}')

    success_count = 0
    failures: list[tuple[str, str]] = []

    for row in selected_rows:
        sample_id = (row.get('sample_id') or '').strip()
        pdf_path = REPO_ROOT / row['pdf_path']
        try:
            candidates = extract_emails_from_pdf(pdf_path, max_pages=args.max_pages)
            normalized_list = [candidate.normalized for candidate in candidates]
            has_grouped = any(candidate.pattern_type.startswith('grouped_') for candidate in candidates)
            usable = bool(candidates)
            ground_truth = parse_ground_truth(row)
            overlap = sorted(email for email in normalized_list if email in ground_truth)
            if usable:
                success_count += 1
            else:
                failures.append((sample_id, 'no email candidates extracted'))
            print(
                f'[SAMPLE] {sample_id} | pdf_path={pdf_path} | count={len(candidates)} | '
                f'grouped_shared={has_grouped} | usable={usable} | normalized={normalized_list}'
            )
            if ground_truth:
                print(f'[GT_OVERLAP] {sample_id} | overlap={overlap} | ground_truth_count={len(ground_truth)}')
        except Exception as exc:
            failures.append((sample_id, str(exc)))
            print(f'[ERROR] {sample_id} | pdf_path={pdf_path} | reason={exc}')

    print(f'[SUMMARY] total={len(selected_rows)} | success={success_count} | failure={len(failures)}')
    if failures:
        print('[FAILED_SAMPLES]')
        for sample_id, reason in failures:
            print(f'- {sample_id}: {reason}')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
