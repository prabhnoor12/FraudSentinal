# FraudSentinal Frontend

Angular 21 frontend for the FraudSentinal fraud detection and operations platform.

## What This App Does

FraudSentinal helps teams:

- score transactions in real time
- review risky decisions
- manage fraud rules
- inspect audit logs
- monitor usage and billing
- keep tenant-scoped data separated correctly

The frontend talks to the backend REST API under `/api/v1`.

## How New Users Should Learn The Product

1. Start at the landing page to understand the platform at a glance.
2. Open the docs page to learn the workflow and integration rules.
3. Sign up or sign in and land on the dashboard.
4. Use review cases, fraud rules, audit, and billing to understand the core loops.
5. Keep the backend request ID and idempotency rules in mind while integrating.

## Public Entry Points

- Landing page: `/`
- Sign in: `/login/sign-in`
- Sign up: `/login/sign-up`
- App dashboard: `/dashboard`
- Docs: `/docs`

## How The Frontend Is Structured

- `src/web/api.ts` is the shared API client.
- `src/web/` contains the feature pages.
- `src/web/web-layout.ts` is the authenticated shell used after sign-in.
- `src/app/app.routes.ts` controls public, auth, and app routes.
- `src/styles.scss` defines the shared UI system and responsive layout.

## API Integration

By default, the frontend calls:

```text
http://localhost:8000/api/v1
```

You can override the backend location by setting the HTML meta tag:

```html
<meta name="fraudsentinel-api-base-url" content="https://your-backend.example.com/api/v1" />
```

The client uses:

- bearer tokens for authenticated user flows
- refresh tokens for silent re-authentication
- `Idempotency-Key` on mutating calls where retry safety matters

## Key Concepts

- Tenant: the organisation boundary used for nearly every read and write.
- Decision: the fraud outcome produced by scoring a transaction.
- Review case: an analyst workflow item created when a decision needs human review.
- Fraud rule: a configurable scoring rule that contributes to the decision outcome.
- Request ID: a trace identifier returned by the backend for support and debugging.

## Running Locally

```bash
npm install
npm start
```

Then open:

```text
http://localhost:4200
```

## Build And Test

```bash
npm run build
npm test
```

If you need the SSR build output:

```bash
npm run build
npm run serve:ssr:fraudsentinel-frontend
```

## Design Notes

- The landing page is public and explains the platform clearly for new users.
- The docs page is public and summarizes purpose, architecture, and integration steps.
- Authenticated pages are protected by the route guard.
- The app keeps a strong `/api/v1` contract so frontend and backend stay aligned.

## For Contributors

- Keep new routes aligned with the `/api/v1` backend contract.
- Prefer the shared API client in `src/web/api.ts` instead of calling `fetch` directly.
- Preserve tenant scoping in UI flows so users cannot cross organisations accidentally.
- Keep the docs page current when adding new workflows or changing core semantics.
