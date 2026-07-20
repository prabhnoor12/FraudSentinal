# FraudSentinal API v1 Contract

## Scope

- All public API routes are served under `/api/v1/...`.
- Swagger UI is available at `/docs`.
- OpenAPI 3.x JSON is available at `/openapi.json`.
- `v1` is the stable public contract for customer integrations.

## Stability Rules

- Additive changes are allowed in `v1`:
  - new optional fields
  - new endpoints
  - new filters or sort options
  - new enum values when clients are documented to tolerate unknown values
- Breaking changes are not allowed in `v1`.
- A new version prefix such as `/api/v2` is required for:
  - required field additions
  - field removals or renames
  - response envelope changes
  - auth mechanism changes
  - incompatible semantic changes

## Change Management

1. Propose the change and identify whether it is additive or breaking.
2. If breaking, create a new versioned route set instead of modifying `v1`.
3. Regenerate and review:
   - OpenAPI
   - Postman collection
   - code examples
   - integration notes
4. Publish release notes for any externally visible addition to `v1`.

## Authentication

### User Sessions

- Interactive users authenticate with `Authorization: Bearer <jwt>`.
- JWTs carry organisation context and are accepted on protected routes.

### Machine Access

- Service-to-service clients authenticate with `X-API-Key`.
- API keys belong to service accounts and carry explicit scopes.
- Keys are fingerprinted for lookup and stored encrypted at rest.
- Expired, revoked, or overdue-for-rotation keys are rejected.

### Scope Enforcement

- API keys must include the scopes required by the route.
- Typical scopes include:
  - `fraud:check`
  - `transactions:read`
  - `transactions:write`
  - `usage:read`
  - `usage:write`
  - `billing:read`
  - `billing:write`
  - `limits:read`
  - `limits:write`

## Request IDs

- Every request receives an `X-Request-ID` response header.
- Clients may send `X-Request-ID`; otherwise the API generates a UUID.
- The same request ID is returned in error payloads and should be used for support and log correlation.

## Error Envelope

All handled API errors follow this shape:

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

### Error Fields

- `code`: machine-readable error identifier
- `message`: human-readable summary
- `details`: structured context for debugging
- `request_id`: request correlation identifier

## List Endpoints

Collection endpoints use a shared paginated response envelope:

```json
{
  "items": [],
  "pagination": {
    "total": 125,
    "limit": 25,
    "offset": 50,
    "next": "/api/v1/transactions?limit=25&offset=75",
    "previous": "/api/v1/transactions?limit=25&offset=25"
  }
}
```

### Shared Query Parameters

- `limit`: page size, clamped by the route maximum
- `offset`: zero-based record offset
- `sort_by`: resource-supported sort field
- `sort_dir`: `asc` or `desc`

### Resource Filters

- Additional filters are resource-specific, such as:
  - `user_id`
  - `status`
  - `event_type`
  - `resource_type`
  - `is_active`
  - `limit_type`

### Current Standardized Collection Routes

- `/api/v1/auth/service-accounts`
- `/api/v1/auth/service-accounts/{service_account_id}/keys`
- `/api/v1/auth/service-accounts/rotation-alerts`
- `/api/v1/transactions`
- `/api/v1/decisions`
- `/api/v1/risk-signals`
- `/api/v1/review-cases`
- `/api/v1/review-cases/queue/my`
- `/api/v1/fraud-rules`
- `/api/v1/audit`
- `/api/v1/usage/events`
- `/api/v1/usage/summaries`
- `/api/v1/user-tracking/events`
- `/api/v1/user-tracking/summaries`
- `/api/v1/billing/plans`
- `/api/v1/billing/records`
- `/api/v1/limit-tracking/limits`
- `/api/v1/limit-tracking/records`
- `/api/v1/sessions`
- `/api/v1/users`
- `/api/v1/organisations`
- `/api/v1/enrichment/ip-geolocation/list`
- `/api/v1/enrichment/bin-lookup/list`

## Idempotency

- `Idempotency-Key` is required on write operations for:
  - `/api/v1/check-fraud`
  - `/api/v1/transactions`
  - `/api/v1/usage`
  - `/api/v1/user-tracking`
  - `/api/v1/limit-tracking`
  - `/api/v1/billing`
- Keys must be unique per logical mutation and stable across retries.
- Retention window: `7 days`
- Reusing the same key with a different payload returns `409 idempotency_key_reused`.

## Rate Limiting

- Public routes may return `429 rate_limit_exceeded`.
- Relevant rate limit headers are included when throttling applies:
  - `Retry-After`
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

## Webhook Signatures

- Outgoing webhook payloads use HMAC-SHA256 over:
  - `{timestamp}.{canonical_json_payload}`
- Canonical JSON means a stable JSON representation without insignificant whitespace.
- Headers:
  - `X-FraudSentinal-Timestamp`
  - `X-FraudSentinal-Signature`
- Consumers should:
  - verify the signature
  - enforce a replay window using the timestamp
  - reject stale or mismatched signatures
