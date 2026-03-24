from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call the Author Email Extractor API with a single PDF path argument.",
    )
    parser.add_argument(
        "pdf_path",
        help="Absolute PDF path, for example C:/path/to/file.pdf or /path/to/file.pdf.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="API base URL. Default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--show-full-response",
        action="store_true",
        help="Print the full API response after the summary.",
    )
    return parser


def parse_structured_payload(response_json: dict[str, Any]) -> dict[str, Any] | None:
    raw = response_json.get("structured_email_string")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def print_summary(response_json: dict[str, Any], payload: dict[str, Any] | None) -> None:
    first_author = None
    first_author_email = None
    first_author_region = None

    if payload:
        first = payload.get("first_author")
        if isinstance(first, dict):
            first_author = first.get("author_norm")
        first_author_email = payload.get("first_author_email")
        first_author_region = payload.get("first_author_region")

    print(f"code: {response_json.get('code')}")
    print(f"message: {response_json.get('message')}")
    print(f"first_author: {first_author}")
    print(f"first_author_email: {first_author_email}")
    print(f"first_author_region: {first_author_region}")


def request_api(pdf_path: str, base_url: str) -> tuple[dict[str, Any], int]:
    endpoint = base_url.rstrip("/") + "/extract-author-emails"
    response = requests.post(
        endpoint,
        json={"pdf_path": pdf_path},
        timeout=120,
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"API returned non-JSON response (status={response.status_code}).") from exc
    return data, response.status_code


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        response_json, status_code = request_api(args.pdf_path, args.base_url)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = parse_structured_payload(response_json)
    print_summary(response_json, payload)

    if args.show_full_response:
        print()
        print("full_response:")
        print(json.dumps(response_json, ensure_ascii=False, indent=2))

    if status_code >= 400:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
