# FraudSentinal API Documentation

## Overview

FraudSentinal is a real-time fraud detection API that scores transactions using configurable rules, signal enrichment (IP geolocation + BIN lookup), and risk-based decisioning.

**Base URL:** `http://localhost:8000`

**Authentication:** Bearer token (JWT) required for all endpoints except `/health` and `/auth/*`

---

## Core Fraud Detection

### POST /check-fraud

The primary endpoint for scoring transactions and making fraud decisions.

**Request Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "user_id": 1,
  "organisation_id": 1,
  "external_transaction_id": "txn_12345",
  "amount": 150.00,
  "currency": "USD",
  "payment_method": "credit_card",
  "channel": "api",
  "customer_id": "cust_12345",
  "customer_email": "customer@example.com",
  "billing_country": "US",
  "shipping_country": "US",
  "ip_address": "192.168.1.1",
  "device_id": "device_12345",
  "account_age_days": 365,
  "transactions_last_24h": 2,
  "failed_attempts_last_24h": 0,
  "metadata": {
    "card_last_four": "4242"
  }
}
```

**Response (200 OK):**
```json
{
  "risk_score": 45.5,
  "decision": "review",
  "reason_codes": ["high_amount", "velocity_spike"],
  "matched_rules": [
    {
      "id": 1,
      "name": "High amount level 1",
      "rule_code": "high_amount_500",
      "weight": 10,
      "reason_code": "high_amount"
    }
  ]
}
```

**Decision Values:**
- `approve` - Transaction is safe to proceed
- `review` - Transaction requires manual review
- `decline` - Transaction should be blocked

**Reason Codes:**
- `high_amount` - Transaction amount is elevated
- `velocity_spike` - Unusual transaction frequency
- `repeated_failed_attempts` - Multiple failed attempts
- `new_account` - Account is recently created
- `cross_border_mismatch` - Billing/shipping country mismatch
- `risky_payment_method` - High-risk payment method
- `missing_device` - No device identifier present
- `manual_entry` - Manual/call center channel
- `low_signal_profile` - No risk signals detected (default)

---

## Signal Enrichment

FraudSentinal enriches transactions with IP geolocation and BIN lookup data for enhanced fraud detection. This happens automatically during the `/check-fraud` call.

### IP Geolocation

Maps IP addresses to geographic locations to detect mismatches.

**Signals Generated:**
- `ip_country_code` - Country from IP geolocation
- `ip_region` - Region/state from IP
- `ip_city` - City from IP
- `ip_billing_country_mismatch` - True if IP country != billing country

### BIN Lookup

Analyzes the first 6 digits of card numbers for risk signals.

**Signals Generated:**
- `card_brand` - Visa, Mastercard, Amex, etc.
- `card_type` - Credit, debit, prepaid
- `issuing_country_code` - Country where card was issued
- `is_prepaid` - True if prepaid card
- `bin_risk_score` - Risk score (0-100) for this BIN

---

## Enrichment API Endpoints

### GET /enrichment/health

Health check for enrichment services.

**Response:**
```json
{
  "status": "healthy",
  "service": "enrichment"
}
```

---

### GET /enrichment/ip-geolocation/lookup

Lookup IP geolocation data for a given IP address.

**Query Parameters:**
- `ip_address` (required) - IP address to lookup

**Response:**
```json
{
  "ip_address": "8.8.8.8",
  "country_code": "US",
  "region": "California",
  "city": "Mountain View",
  "latitude": 37.386,
  "longitude": -122.0838,
  "isp": "Google LLC",
  "data_source": "local"
}
```

---

### GET /enrichment/bin-lookup/lookup

Lookup BIN data for a card.

**Query Parameters:**
- `bin_number` (optional) - First 6 digits of card
- `card_number` (optional) - Full card number (BIN will be extracted)

**Response:**
```json
{
  "bin_number": "424242",
  "card_brand": "Visa",
  "card_type": "Credit",
  "issuing_bank": "Chase Bank",
  "issuing_country_code": "US",
  "is_prepaid": false,
  "risk_score": 10,
  "data_source": "local"
}
```

---

### GET /enrichment/signals/test

Test endpoint to verify enrichment signals are working.

**Query Parameters:**
- `ip_address` (optional) - IP to test
- `card_number` (optional) - Card to test
- `billing_country` (optional) - Billing country for mismatch detection

**Response:**
```json
{
  "ip_address": "8.8.8.8",
  "card_number": "424242******",
  "billing_country": "US",
  "signals": {
    "ip_geolocation_available": true,
    "ip_country": "US",
    "ip_billing_country_mismatch": false,
    "bin_lookup_available": true,
    "card_brand": "Visa",
    "is_prepaid": false
  },
  "enrichment_data_for_rules": {
    "ip_country_code": "US",
    "card_brand": "Visa",
    "is_prepaid": false
  },
  "data_source": "local"
}
```

---

### POST /enrichment/seed

Seed the database with sample IP geolocation and BIN lookup data.

**Query Parameters:**
- `confirm` (required) - Must be `true` to confirm seeding

**Response:**
```json
{
  "success": true,
  "ip_geolocations": 12,
  "bin_lookups": 15,
  "message": "Enrichment data seeded successfully"
}
```

---

## Authentication

All endpoints except `/health` and `/auth/*` require a JWT Bearer token.

**Header:**
```
Authorization: Bearer <jwt_token>
```

**Token Payload:**
```json
{
  "sub": "user@example.com",
  "user_id": 1,
  "org_id": 1,
  "exp": 1234567890
}
```

The `org_id` claim is used for tenant isolation - users can only access their organization's data.

---

## Error Responses

**400 Bad Request:**
```json
{
  "detail": "Invalid request parameters"
}
```

**401 Unauthorized:**
```json
{
  "detail": "Not authenticated"
}
```

**403 Forbidden:**
```json
{
  "detail": "Access denied"
}
```

**404 Not Found:**
```json
{
  "detail": "Resource not found"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "amount"],
      "msg": "Amount must be greater than 0",
      "type": "value_error"
    }
  ]
}
```

---

## Rate Limits

- **General API:** 120 requests per 60 seconds
- **IP-based:** 300 requests per 60 seconds
- **Health check:** Unlimited

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1234567890
```

---

## Testing the API

### Quick Test with curl

**Health check:**
```bash
curl http://localhost:8000/health
```

**Check-fraud with enrichment:**
```bash
curl -X POST http://localhost:8000/check-fraud \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "organisation_id": 1,
    "amount": 500,
    "currency": "USD",
    "payment_method": "credit_card",
    "channel": "api",
    "ip_address": "8.8.8.8",
    "billing_country": "US"
  }'
```

**Test enrichment signals:**
```bash
curl "http://localhost:8000/enrichment/signals/test?ip_address=8.8.8.8&billing_country=US" \
  -H "Authorization: Bearer <token>"
```

---

## Architecture Notes

**Zero External API Dependencies:**
- All enrichment data (IP geolocation, BIN lookup) is stored locally in SQLite
- No third-party API calls during fraud checks
- Sub-100ms response times for fraud scoring

**Signal Enrichment Flow:**
1. Transaction received at `/check-fraud`
2. Enrichment service queries local IP and BIN tables
3. Signals merged with transaction data
4. Rules evaluated against enriched data
5. Risk score and decision returned

**Tenant Isolation:**
- JWT `org_id` claim enforces organization boundaries
- All queries filtered by `organisation_id`
- Users cannot access other organizations' data
