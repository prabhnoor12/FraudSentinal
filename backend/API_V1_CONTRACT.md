# FraudSentinal API v1 Contract

## Versioning

- All public endpoints are served under `/api/v1/...`.
- `v1` request and response schemas are contract-frozen.
- Any breaking field rename, required-field addition, enum behavior change, or response-shape change must ship under a new version prefix such as `/api/v2`.

## Change Management

1. Additive changes only in `v1`: optional fields, new endpoints, new enum values when consumers are documented to tolerate them.
2. Breaking changes require:
   - an ADR or release proposal,
   - schema diff review,
   - new versioned route registration,
   - updated Postman collection and code examples,
   - backward-compatibility notice in release notes.
3. Existing `v1` examples, SDK snippets, and OpenAPI docs must be regenerated from the live application before release.

## Error Format

```json
{
  "success": false,
  "error": {
    "code": "schema_validation_error",
    "message": "Validation failed",
    "details": {
      "errors": []
    },
    "request_id": "1fca8a08-95cb-4d57-9c11-5a9f3b8f64d9"
  }
}
```

## Request IDs

- Every request receives an `X-Request-ID` header.
- Clients may supply `X-Request-ID`; otherwise the API generates a UUID.
- The same request ID is returned in error payloads and response headers.

## Idempotency

- `Idempotency-Key` is required on write operations for:
  - `/api/v1/check-fraud`
  - `/api/v1/transactions`
  - `/api/v1/usage`
  - `/api/v1/user-tracking`
  - `/api/v1/limit-tracking`
  - `/api/v1/billing`
- Keys should be unique per logical operation and kept stable across retries.
- Retention window: `7 days`
- Reusing the same key with a different payload returns `409 idempotency_key_reused`.

## API Key Auth

- Machine clients authenticate with `X-API-Key`.
- API keys belong to service accounts and are scope-limited.
- Keys are fingerprinted for lookup and encrypted at rest for controlled storage.
- Expired, revoked, or overdue-for-rotation keys are rejected.

## Webhook Signatures

- Outgoing webhook payloads use HMAC-SHA256 over:
  - `{timestamp}.{canonical_json_payload}`
- Headers:
  - `X-FraudSentinal-Timestamp`
  - `X-FraudSentinal-Signature`
- Consumers should reject signatures outside their replay window and verify against the shared signing secret.
