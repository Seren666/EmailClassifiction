from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import build_response_from_payload


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


def load_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_success_response(
    response: dict[str, Any],
    response_schema: dict[str, Any],
    output_schema: dict[str, Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        validate(instance=response, schema=response_schema)
    except ValidationError as exc:
        return False, f"envelope schema validation failed: {exc.message}", None

    if response.get("code") != "OK":
        return False, f"expected OK response but got {response.get('code')}", None

    structured_email_string = response.get("structured_email_string")
    if not isinstance(structured_email_string, str) or not structured_email_string:
        return False, "structured_email_string is empty on success", None

    try:
        payload = json.loads(structured_email_string)
    except json.JSONDecodeError as exc:
        return False, f"structured_email_string is not valid JSON: {exc}", None

    try:
        validate(instance=payload, schema=output_schema)
    except ValidationError as exc:
        return False, f"inner payload schema validation failed: {exc.message}", payload

    return True, "response and inner payload both passed schema validation", payload


def validate_error_response(
    response: dict[str, Any],
    response_schema: dict[str, Any],
    expected_code: str,
) -> tuple[bool, str]:
    try:
        validate(instance=response, schema=response_schema)
    except ValidationError as exc:
        return False, f"envelope schema validation failed: {exc.message}"

    if response.get("code") != expected_code:
        return False, f"expected code={expected_code} but got {response.get('code')}"
    if response.get("structured_email_string") != "":
        return False, "error response should keep structured_email_string empty"
    return True, "error envelope is valid"


def create_no_email_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "A Simple Test Paper\nAlice Zhang\nDepartment of Examples\nNo email is shown here.")
    doc.save(path)
    doc.close()


def create_invalid_pdf(path: Path) -> None:
    path.write_text("this is not a valid pdf file", encoding="utf-8")


def prepare_error_case_dir(root: Path) -> Path:
    temp_root = root / ".step8_smoke_artifacts"
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def cleanup_error_case_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for the Step 8 FastAPI envelope logic.")
    parser.add_argument("--limit", type=int, default=12, help="Number of positive PDF samples to test.")
    parser.add_argument("--show-samples", type=int, default=2, help="Number of successful response samples to show.")
    parser.add_argument("--seed", type=int, default=47, help="Random seed for showcase sampling.")
    args = parser.parse_args()

    csv_path = REPO_ROOT / "data" / "samples_v1.csv"
    response_schema = load_schema(REPO_ROOT / "schemas" / "response.envelope.schema.json")
    output_schema = load_schema(REPO_ROOT / "schemas" / "output.schema.json")
    rows = load_rows(csv_path)
    selected_rows = choose_samples(rows, args.limit)

    print(f"[INFO] CSV source: {csv_path}")
    print(f"[INFO] API smoke positive sample count: {len(selected_rows)}")

    success_count = 0
    failures: list[tuple[str, str]] = []
    showcase_pool: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    for row in selected_rows:
        sample_id = (row.get("sample_id") or "").strip()
        pdf_path = REPO_ROOT / row["pdf_path"]
        try:
            response, status_code = build_response_from_payload({"pdf_path": str(pdf_path)})
            ok, reason, payload = validate_success_response(response, response_schema, output_schema)
            if ok and payload is not None:
                success_count += 1
                showcase_pool.append((sample_id, response, payload))
            else:
                failures.append((sample_id, reason))

            stats = response.get("stats") or {}
            payload_stats = payload.get("stats") if payload else {}
            print(
                f"[SAMPLE] {sample_id} | status={status_code} | code={response.get('code')} | "
                f"message={response.get('message')} | author_count={stats.get('author_count')} | "
                f"email_count={stats.get('email_count')} | pair_count={stats.get('pair_count')} | "
                f"first_author_exists={payload_stats.get('first_author_found') if payload else None} | "
                f"first_author_email_exists={payload_stats.get('has_first_author_email') if payload else None}"
            )
            print(f"[EVAL] {sample_id} | reason={reason}")
        except Exception as exc:
            failures.append((sample_id, str(exc)))
            print(f"[ERROR] {sample_id} | reason={exc}")

    print(f"[SUMMARY] positive_total={len(selected_rows)} | success={success_count} | failure={len(failures)}")
    if failures:
        print("[FAILED_SAMPLES]")
        for sample_id, reason in failures:
            print(f"- {sample_id}: {reason}")

    print("[ERROR_CASES]")
    error_success_count = 0
    error_failures: list[tuple[str, str]] = []
    temp_root = prepare_error_case_dir(REPO_ROOT)
    try:
        invalid_pdf = temp_root / "broken.pdf"
        no_email_pdf = temp_root / "no_email.pdf"
        missing_pdf = temp_root / "missing.pdf"
        create_invalid_pdf(invalid_pdf)
        create_no_email_pdf(no_email_pdf)

        error_cases = [
            ("INVALID_REQUEST", {}, "INVALID_REQUEST"),
            ("PATH_NOT_FOUND", {"pdf_path": str(missing_pdf)}, "PATH_NOT_FOUND"),
            ("PARSE_FAILED", {"pdf_path": str(invalid_pdf)}, "PARSE_FAILED"),
            ("NO_EMAIL_FOUND", {"pdf_path": str(no_email_pdf)}, "NO_EMAIL_FOUND"),
        ]

        for case_id, payload, expected_code in error_cases:
            response, status_code = build_response_from_payload(payload)
            ok, reason = validate_error_response(response, response_schema, expected_code)
            if ok:
                error_success_count += 1
            else:
                error_failures.append((case_id, reason))
            print(
                f"[ERROR_SAMPLE] {case_id} | status={status_code} | code={response.get('code')} | "
                f"message={response.get('message')} | reason={reason}"
            )
    finally:
        cleanup_error_case_dir(temp_root)

    print(f"[ERROR_SUMMARY] total={4} | success={error_success_count} | failure={len(error_failures)}")
    if error_failures:
        for sample_id, reason in error_failures:
            print(f"- {sample_id}: {reason}")

    if showcase_pool:
        sample_count = min(args.show_samples, len(showcase_pool))
        chosen = random.Random(args.seed).sample(showcase_pool, sample_count)
        print("[SHOWCASE]")
        for sample_id, response, payload in chosen:
            print(f"- {sample_id} | envelope={json.dumps(response, ensure_ascii=False)}")
            compact_payload = {
                "first_author": payload.get("first_author"),
                "first_author_email": payload.get("first_author_email"),
                "first_author_region": payload.get("first_author_region"),
                "stats": payload.get("stats"),
            }
            print(json.dumps(compact_payload, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
