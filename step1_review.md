# Step 1 Review

## What Was Frozen

This step only freezes the API contract and the output schema for `POST /extract-author-emails`.

Created files:
- `docs/api_v1.md`
- `schemas/output.schema.json`
- `schemas/response.envelope.schema.json`
- `examples/request.json`
- `examples/response.success.json`
- `examples/response.error.path_not_found.json`
- `examples/response.error.parse_failed.json`

Frozen decisions:
- Route is `POST /extract-author-emails`.
- Request body only requires `pdf_path` in V1.
- Top-level response fields are always `structured_email_string`, `stats`, `code`, and `message`.
- `structured_email_string` represents a JSON-serialized object whose schema is frozen in `schemas/output.schema.json`.
- `schemas/response.envelope.schema.json` validates the outer API response envelope, while `schemas/output.schema.json` validates only the deserialized inner payload.
- `first_author` in V1 means the first author by author order.
- `first_author.reason` defaults to `first_by_author_order`.
- `co_first_authors` and `equal_contribution_detected` are reserved but not treated as a hard acceptance target in this step.
- Field naming follows an additive-compatibility rule: later versions should prefer adding fields instead of changing old field meanings.

## Conservative Choices Made

- `first_author` is allowed to be `null` so the contract does not force a fake placeholder object when author extraction fails.
- `first_author_email` and `first_author_region` are reserved as optional additive fields because Section 8 marks them as optional.
- Inner objects use minimal required fields plus `additionalProperties: true` to reduce the chance of breaking later iterations.
- Error responses keep the same top-level field set; `structured_email_string` is an empty string on error.
- Outer `stats` and inner payload `stats` use the same key set in V1 to avoid two different summary shapes.

## Ambiguities Not Expanded

1. `debug=true`
   Section 8 mentions it as optional. This step does not freeze `debug` into the request contract. It is left for later additive introduction.

2. Error examples coverage
   Section 8 also mentions `NO_EMAIL_FOUND` and `INTERNAL_ERROR`. They are documented in `docs/api_v1.md` but no separate example files were created in this step because the user only required the two named error examples.

3. Payload detail depth
   The monthly plan fixes the top-level payload structure, but not every nested field. This step therefore freezes only minimal nested required fields and leaves room for later additive detail.

## Not Done By Design

- No PDF parsing
- No email extraction
- No author extraction
- No matching logic
- No sample set
- No dependency installation
- No Step 2 work
