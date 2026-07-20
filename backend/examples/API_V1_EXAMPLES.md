# FraudSentinal API v1 Examples

## Python: Service Account Key Creation

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

api_key = requests.post(
    f"{BASE_URL}/api/v1/auth/service-accounts/{service_account_id}/keys",
    headers={"Authorization": f"Bearer {JWT}"},
    json={
        "name": "primary",
        "scopes": ["fraud:check", "transactions:write", "transactions:read"],
    },
    timeout=30,
)
api_key.raise_for_status()
print(api_key.json()["raw_key"])
```

## Python: Fraud Check Submission

```python
import requests
import uuid

BASE_URL = "http://localhost:8000"
API_KEY = "fs_live_your_key"

response = requests.post(
    f"{BASE_URL}/api/v1/check-fraud",
    headers={
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
print(response.json())
```

## Node.js: Usage Event Ingestion

```javascript
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

console.log(await response.json());
```

## Go: Billing Mutation

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
	fmt.Println(resp.Status, strings.TrimSpace(string(payload)))
}
```

## Node.js: Webhook Signature Verification

```javascript
import crypto from "node:crypto";

function verifyWebhook(payload, timestamp, signature, secret) {
  const canonicalPayload = JSON.stringify(payload);
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
