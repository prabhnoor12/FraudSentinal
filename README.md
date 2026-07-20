# FraudSentinal

Real-time fraud detection and risk operations platform for e-commerce, fintech, and SaaS workflows.

## Overview

FraudSentinal exposes a versioned public API for:

- fraud scoring
- transaction and review workflows
- usage metering
- billing operations
- audit visibility
- tenant and service-account administration
- enrichment data access

## Public API

- Base URL: `http://localhost:8000`
- Version prefix: `/api/v1`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Authentication

- `Authorization: Bearer <jwt>` for interactive user access
- `X-API-Key: <service_account_key>` for machine-to-machine access

## Shared v1 Conventions

- Mutating calls use `Idempotency-Key`
- Responses include `X-Request-ID`
- Collection endpoints return:

```json
{
  "items": [],
  "pagination": {
    "total": 0,
    "limit": 25,
    "offset": 0,
    "next": null,
    "previous": null
  }
}
```

## Quick Start

### Run The Backend

```bash
cd backend
python -m uvicorn app:app --reload
```

### Quick Fraud Check

```bash
curl -X POST http://localhost:8000/api/v1/check-fraud \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_SERVICE_ACCOUNT_KEY" \
  -H "Idempotency-Key: fraud-check-demo-001" \
  -d '{
    "user_id": 1,
    "organisation_id": 1,
    "amount": 99.99,
    "currency": "USD",
    "payment_method": "card",
    "channel": "api",
    "customer_id": "cust_demo"
  }'
```

## Developer Resources

- Contract reference: `backend/API_V1_CONTRACT.md`
- API reference: `API_DOCUMENTATION.md`
- Examples: `backend/examples/API_V1_EXAMPLES.md`
- Postman collection: `postman/FraudSentinal API v1.postman_collection.json`

## Core v1 Routes

- `POST /api/v1/check-fraud`
- `GET /api/v1/transactions`
- `GET /api/v1/review-cases`
- `GET /api/v1/usage/events`
- `GET /api/v1/billing/records`
- `GET /api/v1/audit`
- `GET /api/v1/enrichment/ip-geolocation/list`

## Security Highlights

- service-account API keys with scopes
- request IDs on all responses
- standardized error envelope
- idempotent write handling with replay protection
- rate limiting and audit logging
- tenant-aware filtering across list endpoints
