# FraudSentinal Pricing Recommendation

## Short Answer

Based on the current backend feature set, a practical starting price is:

- `Free / Sandbox`: `0 USD/month` for testing and evaluation
- `Starter`: `99 USD/month`
- `Growth`: `399 USD/month`
- `Scale`: `1,499 USD/month`
- `Enterprise`: custom pricing

The main usage unit should be `fraud checks per month`, with overage pricing for additional volume.

---

## What You Can Realistically Charge Today

This backend is not just a basic scoring endpoint. It already includes:

- Real-time fraud scoring via `POST /check-fraud`
- Configurable fraud rules and rule management APIs
- IP geolocation and BIN enrichment
- Velocity-based risk signals
- Device fingerprinting and new-device detection
- Review case workflows
- Audit logging and audit export endpoints
- JWT auth, refresh/logout, password reset, and MFA
- Tenant isolation by organisation
- Rate limiting, metrics, and Redis-backed performance improvements

That means you can price it as a `fraud decisioning API`, not as a generic internal backend.

At the same time, the product still looks like an `early commercial / strong MVP` rather than a fully mature enterprise platform, because:

- ML scoring exists as a foundation but still needs calibration before broad rollout
- External observability and alerting are not yet fully productized
- Formal managed-service operations, onboarding, and SLA processes are not clearly packaged yet

Because of that, the right move is `mid-market pricing`, not bargain-basement pricing and not top-of-market enterprise pricing.

---

## Recommended Public Pricing

### 1. Free / Sandbox

**Price:** `0 USD/month`

**Includes:**

- Up to `1,000 fraud checks/month`
- Basic access to `/check-fraud`
- Test access to enrichment features
- Basic API evaluation for one team
- No SLA
- Community or best-effort support

**Purpose:** Remove friction for demos, pilots, and early adoption.

---

### 2. Starter

**Price:** `99 USD/month`

**Included usage:** `10,000 fraud checks/month`

**Overage:** `0.015 USD` per extra fraud check

**Includes:**

- Real-time fraud scoring
- Rule-based decisioning
- IP geolocation and BIN enrichment
- Organisation-level isolation
- JWT auth and refresh flow
- Basic metrics and rate limiting
- Email support

**Best for:** small SaaS apps, early fintech products, and startups validating fraud controls.

---

### 3. Growth

**Price:** `399 USD/month`

**Included usage:** `100,000 fraud checks/month`

**Overage:** `0.008 USD` per extra fraud check

**Includes everything in Starter, plus:**

- Velocity signals
- Device fingerprinting
- Review case workflows
- Audit logs and audit export APIs
- MFA support
- Higher request limits
- Faster support response

**Best for:** teams that need stronger controls, internal reviews, and auditability.

---

### 4. Scale

**Price:** `1,499 USD/month`

**Included usage:** `500,000 fraud checks/month`

**Overage:** `0.004 USD` per extra fraud check

**Includes everything in Growth, plus:**

- Redis-backed shared caching for higher throughput deployments
- Advanced rollout support for production traffic
- Access to hybrid scoring enablement when you are ready to validate it
- Priority support
- Higher volume limits and rollout guidance

**Best for:** serious production workloads where fraud checks are core to revenue protection.

---

### 5. Enterprise

**Price:** `Custom`

**Recommended starting range:** `2,500 USD/month` and up, or annual contract pricing

**Offer this when the customer needs:**

- Multi-million monthly fraud checks
- Dedicated environments
- Private deployment or self-hosted options
- Custom onboarding and integration help
- Custom support terms
- Security and procurement review support

**Best for:** larger fintech, marketplaces, payment platforms, and regulated teams.

---

## Why This Pricing Fits The Current Backend

### You Can Charge More Than A Simple API

The backend already has meaningful product value:

- It does decisioning, not just raw data lookup
- It supports explainable rules and reason codes
- It has layered risk signals, not only static thresholds
- It includes operator-facing workflows like review cases and audit logs
- It has security features expected in commercial software

If you price too low, you position it like a utility endpoint instead of a fraud-control product.

### You Should Not Charge Like A Fully Mature Enterprise Vendor Yet

The current system is strong, but you should avoid pricing it like a category leader until you have:

- Proven production benchmarking across real customer traffic
- Mature monitoring and alerting
- Calibrated ML scoring in production
- Clear SLA and support commitments
- Sales-ready compliance packaging

That is why the recommended pricing sits in a practical middle ground.

---

## Suggested Billing Metric

Use `successful fraud check requests` as the main billable unit.

A clean billing rule is:

- Count every successful call to `POST /check-fraud`
- Do not bill health checks
- Do not bill internal admin operations like rule edits or audit exports
- Optionally bill enrichment-only endpoints only on higher plans if they are used heavily

This keeps pricing understandable and easy to explain.

---

## Add-Ons You Can Sell

- `Priority support`: `250-750 USD/month`
- `Implementation / onboarding package`: `500-3,000 USD` one-time
- `Private deployment / self-hosted license`: `15,000-40,000 USD/year`
- `Custom rule design or fraud tuning`: consulting-based pricing

These add-ons can materially increase revenue without changing the core product.

---

## Positioning Advice

If you are selling this now, the safest public message is:

`FraudSentinal is a real-time fraud decisioning API for growing platforms that need configurable rules, enrichment, review workflows, and strong security without building everything in-house.`

That message matches the current backend well.

---

## Recommended Launch Version

If you want the simplest launch:

- Publish `Free`, `Starter`, and `Growth`
- Keep `Scale` and `Enterprise` as sales-led plans
- Bill primarily on `monthly fraud checks`
- Start with annual discounts later, not on day one

This gives you a simple pricing page and enough room to grow with customers.

---

## Final Recommendation

If you want one concise answer:

- Start at `99 USD/month` for paid usage
- Make `399 USD/month` your main target plan
- Use `1,499 USD/month` as your serious production tier
- Quote enterprise separately

That is a realistic price band for the backend as it exists today.
