# FraudSentinal API v1 Documentation

## Overview

FraudSentinal exposes a versioned public API for fraud scoring, transaction review, usage metering, billing, tenant administration, and enrichment data access.

- Base URL: `http://localhost:8000`
- Public version prefix: `/api/v1`
- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

## Authentication

### Bearer JWT

Use JWT authentication for interactive user workflows.

```http
Authorization: Bearer <jwt_token>
```

### API Keys

Use service-account API keys for machine-to-machine integrations.

```http
X-API-Key: fs_live_xxxxxxxxxxxxx
```

### Auth Notes

- JWTs and API keys both enforce organisation isolation.
- API keys must include the scopes required by each route.
- Interactive user routes, such as service-account management, require JWT authentication.

## Core Headers

### Required On JSON Requests

```http
Content-Type: application/json
```

### Recommended On All Requests

```http
X-Request-ID: your-correlation-id
```

### Required On Mutating Public API Calls

```http
Idempotency-Key: your-stable-operation-id
```

## Standard Response Shapes

### Error Envelope

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

### Paginated List Envelope

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

### Shared List Query Parameters

- `limit`
- `offset`
- `sort_by`
- `sort_dir`

Additional filters are route-specific.

## Authentication Endpoints

### POST /api/v1/auth/register

Register a user and create an organisation when `organisation_name` is provided.

### POST /api/v1/auth/login

Exchange user credentials for JWT access and refresh tokens.

### GET /api/v1/auth/me

Return the authenticated user profile.

### POST /api/v1/auth/service-accounts

Create a service account for machine access.

### GET /api/v1/auth/service-accounts

List service accounts using the shared paginated envelope.

Supported query params:

- `limit`
- `offset`
- `sort_by`
- `sort_dir`

### POST /api/v1/auth/service-accounts/{service_account_id}/keys

Issue a new API key for a service account.

### GET /api/v1/auth/service-accounts/{service_account_id}/keys

List API keys for a service account using the shared paginated envelope.

## Fraud Scoring

### POST /api/v1/check-fraud

The primary fraud scoring endpoint.

Required headers:

```http
Content-Type: application/json
Idempotency-Key: fraud-check-001
X-API-Key: fs_live_xxxxxxxxxxxxx
```

Example request body:

```json
{
  "user_id": 1,
  "organisation_id": 1,
  "external_transaction_id": "txn_12345",
  "amount": 150.0,
  "currency": "USD",
  "payment_method": "card",
  "channel": "api",
  "customer_id": "cust_12345",
  "billing_country": "US",
  "shipping_country": "US",
  "ip_address": "8.8.8.8",
  "device_id": "device_12345",
  "metadata": {
    "card_last_four": "4242"
  }
}
```

## Operational Collections

### GET /api/v1/transactions

List transactions for the authenticated organisation.

Supported query params:

- `user_id`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

### GET /api/v1/review-cases

List review cases with filters for investigation workflows.

Supported query params:

- `transaction_id`
- `decision_id`
- `status`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

### GET /api/v1/decisions

List fraud decisions for the tenant.

### GET /api/v1/risk-signals

List risk signals for a decision or transaction.

## Usage And Billing

### GET /api/v1/usage/events

List usage events with the shared paginated envelope.

Supported query params:

- `user_id`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

### GET /api/v1/usage/summaries

List usage summaries with the shared paginated envelope.

### GET /api/v1/billing/plans

List billing plans with the shared paginated envelope.

Supported query params:

- `is_active`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

### GET /api/v1/billing/records

List billing records with the shared paginated envelope.

Supported query params:

- `user_id`
- `status`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

## Limit Tracking And Sessions

### GET /api/v1/limit-tracking/limits

List usage limits for the authenticated organisation.

### GET /api/v1/limit-tracking/records

List usage records associated with limits in the authenticated organisation.

### GET /api/v1/sessions

List user sessions visible within the authenticated organisation.

Supported query params:

- `user_id`
- `status_filter`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

## Tenant Administration

### GET /api/v1/users

List users in the authenticated organisation using the shared paginated envelope.

### GET /api/v1/organisations

List visible organisations for the authenticated caller. In the current tenant-scoped mode, non-admin users receive their own organisation in a paginated envelope.

## Audit

### GET /api/v1/audit

List audit logs for the authenticated organisation. This route requires an admin user.

Supported query params:

- `event_type`
- `resource_type`
- `user_id`
- `start_date`
- `end_date`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

## Enrichment

### GET /api/v1/enrichment/health

Health check for the enrichment subsystem.

### GET /api/v1/enrichment/ip-geolocation/lookup

Lookup a single IP address.

### GET /api/v1/enrichment/ip-geolocation/list

List local IP geolocation records using the shared paginated envelope.

Supported query params:

- `country_code`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

### GET /api/v1/enrichment/bin-lookup/lookup

Lookup a BIN by `bin_number` or `card_number`.

### GET /api/v1/enrichment/bin-lookup/list

List local BIN records using the shared paginated envelope.

Supported query params:

- `card_brand`
- `issuing_country`
- `high_risk_only`
- `limit`
- `offset`
- `sort_by`
- `sort_dir`

## Idempotency

`Idempotency-Key` is required for write operations under:

- `/api/v1/check-fraud`
- `/api/v1/transactions`
- `/api/v1/usage`
- `/api/v1/user-tracking`
- `/api/v1/limit-tracking`
- `/api/v1/billing`

Rules:

- Reuse the same key when retrying the same logical operation.
- Do not reuse the same key for a different payload.
- Duplicate submissions with the same key and payload replay the stored response.

## Rate Limiting

Throttle responses may include:

```http
Retry-After: 60
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1234567890
```

## Developer Resources

- Contract reference: `backend/API_V1_CONTRACT.md`
- Runnable examples: `backend/examples/API_V1_EXAMPLES.md`
- Postman collection: `postman/FraudSentinal API v1.postman_collection.json`

## Quick Test

### Fraud Check With API Key

```bash
curl -X POST http://localhost:8000/api/v1/check-fraud \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fs_live_xxxxxxxxxxxxx" \
  -H "Idempotency-Key: fraud-check-demo-001" \
  -d '{
    "user_id": 1,
    "organisation_id": 1,
    "amount": 500,
    "currency": "USD",
    "payment_method": "card",
    "channel": "api",
    "ip_address": "8.8.8.8",
    "billing_country": "US"
  }'
```
- JWT `org_id` claim enforces organization boundaries
- All queries filtered by `organisation_id`
- Users cannot access other organizations' data
