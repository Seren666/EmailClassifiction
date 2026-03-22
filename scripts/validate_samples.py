from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "samples_v1.csv"
REQUIRED_COLUMNS = ["sample_id", "pdf_path", "file_exists", "source_format_guess", "layout_guess", "has_corresponding_author_marker", "has_equal_contribution_note", "has_shared_or_group_email", "ground_truth_authors_json", "ground_truth_first_author_json", "ground_truth_co_first_authors_json", "ground_truth_emails_json", "ground_truth_pairs_json", "ground_truth_email_regions_json", "annotation_status", "notes"]
JSON_COLUMNS = ["ground_truth_authors_json", "ground_truth_first_author_json", "ground_truth_co_first_authors_json", "ground_truth_emails_json", "ground_truth_pairs_json", "ground_truth_email_regions_json"]
ALLOWED_STATUSES = {"todo", "in_progress", "done", "needs_review", "annotated", "reviewed", "blocked"}

def parse_bool_string(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "true": return True
    if normalized == "false": return False
    return None

def main() -> int:
    errors = []
    if not CSV_PATH.exists():
        print(f"[ERROR] CSV file not found: {CSV_PATH}")
        return 1
    try:
        with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
    except Exception as exc:
        print(f"[ERROR] Failed to read CSV: {CSV_PATH}")
        print(f"        {exc}")
        return 1
    print(f"[INFO] CSV loaded: {CSV_PATH}")
    print(f"[INFO] Header column count: {len(fieldnames)}")
    print(f"[INFO] Data row count: {len(rows)}")
    missing_columns = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
    else:
        print(f"[OK] Required columns present: {', '.join(REQUIRED_COLUMNS)}")
    row_success_count = 0
    for row_number, row in enumerate(rows, start=2):
        row_errors_before = len(errors)
        sample_id = (row.get("sample_id") or "").strip() or f"<row {row_number}>"
        status = (row.get("annotation_status") or "").strip()
        if status not in ALLOWED_STATUSES:
            errors.append(f"Row {row_number} ({sample_id}): invalid annotation_status={status!r}; allowed={sorted(ALLOWED_STATUSES)}")
        file_exists_raw = row.get("file_exists") or ""
        file_exists = parse_bool_string(file_exists_raw)
        if file_exists is None:
            errors.append(f"Row {row_number} ({sample_id}): file_exists must be 'true' or 'false', got {file_exists_raw!r}")
        elif file_exists:
            pdf_path_raw = (row.get("pdf_path") or "").strip()
            if not pdf_path_raw:
                errors.append(f"Row {row_number} ({sample_id}): pdf_path is required when file_exists=true")
            elif not (ROOT / pdf_path_raw).exists():
                errors.append(f"Row {row_number} ({sample_id}): file_exists=true but path not found: {pdf_path_raw}")
        for column in JSON_COLUMNS:
            raw_value = row.get(column)
            if raw_value is None or raw_value.strip() == "":
                errors.append(f"Row {row_number} ({sample_id}): {column} is blank; use [] or null instead")
                continue
            try:
                json.loads(raw_value)
            except json.JSONDecodeError as exc:
                errors.append(f"Row {row_number} ({sample_id}): {column} is not valid JSON - {exc.msg}")
        if len(errors) == row_errors_before:
            row_success_count += 1
            print(f"[OK] Row {row_number} ({sample_id}) passed.")
        else:
            print(f"[WARN] Row {row_number} ({sample_id}) failed. See errors below.")
    print(f"[INFO] Rows passed: {row_success_count}/{len(rows)}")
    if errors:
        print("[FAIL] Validation failed.")
        for issue in errors:
            print(f" - {issue}")
        return 1
    print("[PASS] Validation passed.")
    print(f"[OK] JSON columns validated: {', '.join(JSON_COLUMNS)}")
    print(f"[OK] annotation_status values validated: {', '.join(sorted(ALLOWED_STATUSES))}")
    print("[OK] file_exists / pdf_path checks passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
