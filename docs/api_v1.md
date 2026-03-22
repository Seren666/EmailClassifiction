# API v1 Freeze

## Scope

This document freezes only Step 1: the external API contract and the JSON shape carried by `structured_email_string`.

Stability rule for V1:
- Prefer adding new fields later.
- Do not change the meaning of existing fields.

## Endpoint

- Method: `POST`
- Route: `/extract-author-emails`
- Content-Type: `application/json`

## Request Body

Required fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `pdf_path` | string | yes | Local path or mounted path to a PDF file. |

Minimal request example:

```json
{
  "pdf_path": "E:/papers/example.pdf"
}
```

## Response Envelope

All responses in V1 keep the same top-level fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `structured_email_string` | string | yes | JSON-serialized structured payload. Empty string on error responses. |
| `stats` | object | yes | Request-level summary counts. In V1 it uses the same shape as the inner payload `stats`. |
| `code` | string | yes | Stable result code. |
| `message` | string | yes | Short human-readable message. |

## Success Response

- HTTP status: `200`
- `code`: `OK`
- `message`: `success`

`structured_email_string` must serialize an object matching [`schemas/output.schema.json`](../schemas/output.schema.json).

Schema scope in V1:
- [`schemas/output.schema.json`](../schemas/output.schema.json) validates the internal payload obtained after JSON-deserializing `structured_email_string`.
- [`schemas/response.envelope.schema.json`](../schemas/response.envelope.schema.json) validates the whole external API response envelope.

Example validation flow:
1. Parse the whole HTTP response body as JSON.
2. Validate that object against `schemas/response.envelope.schema.json`.
3. Read `structured_email_string` from the parsed response.
4. JSON-deserialize that string into an inner payload object.
5. Validate the inner payload object against `schemas/output.schema.json`.

## Error Responses

The following result codes are frozen in V1:

| HTTP status | `code` | Meaning |
| --- | --- | --- |
| `400` | `INVALID_REQUEST` | Request body is invalid, including missing or empty `pdf_path`. |
| `404` | `PATH_NOT_FOUND` | `pdf_path` does not exist or is not reachable. |
| `422` | `PARSE_FAILED` | PDF exists but parsing/extraction failed. |
| `422` | `NO_EMAIL_FOUND` | PDF was parsed but no email candidate was extracted. |
| `500` | `INTERNAL_ERROR` | Unexpected internal failure. |

Error envelope rule in V1:
- `structured_email_string` is `""`.
- `stats` remains present and uses zero values when no partial result is available.

## Structured Payload in `structured_email_string`

Required top-level fields inside the serialized payload:

| Field | Type | Description |
| --- | --- | --- |
| `authors` | array | Ordered author list. |
| `first_author` | object or null | V1 means the first author by author order when author extraction succeeds. |
| `co_first_authors` | array | Reserved extension field for future equal-contribution handling. |
| `equal_contribution_detected` | boolean | Reserved extension flag for future equal-contribution detection. |
| `emails` | array | Extracted email list. |
| `pairs` | array | Author-email pair list. |
| `shared_emails` | array | Emails associated with multiple authors or retained as shared email groups. |
| `unmatched_authors` | array | Authors without a resolved email match. |
| `unmatched_emails` | array | Emails without a resolved author match. |
| `stats` | object | Structured-result summary counts. |

Optional additive fields already reserved in V1:

| Field | Type | Description |
| --- | --- | --- |
| `first_author_email` | string or null | Present only when the first author is matched to an email. |
| `first_author_region` | string or null | Present only when the first author email has a region label. Allowed values: `CN`, `OVERSEAS`, `UNKNOWN`. |

### `first_author` V1 Definition

V1 freezes `first_author` as:
- the first author in author order;
- not the correspondence author;
- not a co-first-author inference result.

Required fields when `first_author` is not null:

| Field | Type | Description |
| --- | --- | --- |
| `author_raw` | string | Original extracted author text. |
| `author_norm` | string | Normalized author text. |
| `source_page` | integer or null | Source page index, 1-based when available. |
| `reason` | string | Default V1 reason is `first_by_author_order`. |

`co_first_authors` and `equal_contribution_detected` are reserved so later versions can add equal-contribution logic without changing existing field meanings.

## `stats` Shape

The outer `stats` object and the inner payload `stats` object use the same frozen keys in V1:

| Field | Type | Description |
| --- | --- | --- |
| `author_count` | integer | Count of extracted authors. |
| `email_count` | integer | Count of extracted emails. |
| `pair_count` | integer | Count of resolved author-email pairs. |
| `shared_email_count` | integer | Count of shared email groups. |
| `unmatched_author_count` | integer | Count of unmatched authors. |
| `unmatched_email_count` | integer | Count of unmatched emails. |
| `first_author_found` | boolean | Whether `first_author` is present. |

## Explicit Non-Goals for Step 1

- No PDF parsing implementation
- No email extraction implementation
- No author extraction implementation
- No sample dataset creation
- No dependency installation for later steps

## File Map

- Contract document: `docs/api_v1.md`
- Structured payload schema: `schemas/output.schema.json`
- Examples: `examples/*.json`
- Review notes: `step1_review.md`
