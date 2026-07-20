# FraudSentinal API v1 Examples

## Notes

- All public routes use the `/api/v1` prefix.
- Mutating API calls should send `Idempotency-Key`.
- List endpoints return `items` plus `pagination`.
- Errors return the shared `success/error` envelope with `request_id`.

## Python: Create Service Account And API Key

```python
import requests

BASE_URL = "http://localhost:8000"
JWT = "YOUR_USER_JWT"

service_account = requests.post(
    f"{BASE_URL}/api/v1/auth/service-accounts",
    headers={"Authorization": f"Bearer {JWT}"},
    json={
        "organisation_id": 1,
        "name": "fraud-worker",
        "description": "Automated fraud submission pipeline",
        "scopes": ["fraud:check", "transactions:write", "transactions:read"],
    },
    timeout=30,
)
service_account.raise_for_status()
service_account_id = service_account.json()["id"]

api_key_response = requests.post(
    f"{BASE_URL}/api/v1/auth/service-accounts/{service_account_id}/keys",
    headers={"Authorization": f"Bearer {JWT}"},
    json={
        "name": "primary",
        "scopes": ["fraud:check", "transactions:write", "transactions:read"],
    },
    timeout=30,
)
api_key_response.raise_for_status()
api_key = api_key_response.json()["raw_key"]
print(api_key)
```

## Python: Submit A Fraud Check

```python
import requests
import uuid

BASE_URL = "http://localhost:8000"
API_KEY = "fs_live_your_key"

response = requests.post(
    f"{BASE_URL}/api/v1/check-fraud",
    headers={
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "Idempotency-Key": str(uuid.uuid4()),
    },
    json={
        "user_id": 1,
        "organisation_id": 1,
        "amount": 149.95,
        "currency": "USD",
        "payment_method": "card",
        "channel": "api",
        "customer_id": "cust_001",
        "metadata": {"source": "checkout"},
    },
    timeout=30,
)
response.raise_for_status()
print("request_id:", response.headers.get("X-Request-ID"))
print(response.json())
```

## Python: Read A Paginated List Endpoint

```python
import requests

BASE_URL = "http://localhost:8000"
JWT = "YOUR_USER_JWT"

response = requests.get(
    f"{BASE_URL}/api/v1/transactions",
    headers={"Authorization": f"Bearer {JWT}"},
    params={
        "limit": 25,
        "offset": 0,
        "sort_by": "created_at",
        "sort_dir": "desc",
    },
    timeout=30,
)
response.raise_for_status()
payload = response.json()

for item in payload["items"]:
    print(item["id"], item["amount"], item["currency"])

print(payload["pagination"])
```

## Node.js: Create A Usage Event

```javascript
import crypto from "node:crypto";

const response = await fetch("http://localhost:8000/api/v1/usage/events", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": process.env.FS_API_KEY,
    "Idempotency-Key": crypto.randomUUID(),
  },
  body: JSON.stringify({
    user_id: 1,
    organisation_id: 1,
    event_type: "fraud_check",
    units: 1,
    unit_type: "request",
    description: "Fraud check usage",
    status: "recorded",
  }),
});

if (!response.ok) {
  throw new Error(await response.text());
}

console.log("request_id:", response.headers.get("x-request-id"));
console.log(await response.json());
```

## Node.js: Read Billing Records

```javascript
const response = await fetch(
  "http://localhost:8000/api/v1/billing/records?status=pending&limit=10&offset=0",
  {
    headers: {
      Authorization: `Bearer ${process.env.FS_JWT}`,
    },
  },
);

if (!response.ok) {
  throw new Error(await response.text());
}

const payload = await response.json();
console.log(payload.items);
console.log(payload.pagination);
```

## Go: Create A Billing Record

```go
package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"strings"
)

func main() {
	body := `{
		"user_id": 1,
		"organisation_id": 1,
		"amount": 25.00,
		"currency": "USD",
		"status": "pending",
		"invoice_id": "inv_demo_001",
		"description": "Monthly platform fee",
		"billing_period_start": "2026-07-01T00:00:00Z",
		"billing_period_end": "2026-07-31T23:59:59Z"
	}`

	req, _ := http.NewRequest("POST", "http://localhost:8000/api/v1/billing/records", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "fs_live_your_key")
	req.Header.Set("Idempotency-Key", "billing-record-demo-001")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	payload, _ := io.ReadAll(resp.Body)
	fmt.Println("status:", resp.Status)
	fmt.Println("request_id:", resp.Header.Get("X-Request-ID"))
	fmt.Println(strings.TrimSpace(string(payload)))
}
```

## Node.js: Verify Webhook Signature

```javascript
import crypto from "node:crypto";

function canonicalize(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalize).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function verifyWebhook(payload, timestamp, signature, secret) {
  const canonicalPayload = canonicalize(payload);
  const expected = crypto
    .createHmac("sha256", secret)
    .update(`${timestamp}.${canonicalPayload}`)
    .digest("hex");

  return crypto.timingSafeEqual(
    Buffer.from(expected, "utf8"),
    Buffer.from(signature, "utf8"),
  );
}
```

## Example Error Handling

```json
{
  "success": false,
  "error": {
    "code": "missing_idempotency_key",
    "message": "Idempotency-Key header is required for this endpoint",
    "details": {
      "header": "Idempotency-Key",
      "retention_days": 7
    },
    "request_id": "a8e297d9-b3a0-4380-8e72-2c07d8e15cd5"
  }
}
```
