# Production Readiness Checklist - FraudSentinal

## Current Rollout State

- Core fraud-scoring improvements are implemented
- Device fingerprinting, persisted velocity checks, hybrid scoring foundation, and metrics are in place
- `GET /metrics` is available for rollout visibility
- `backend/scripts/load_test_check_fraud.py` provides a reproducible `/check-fraud` benchmark

## Before Running The Benchmark

1. Run the latest Alembic migrations.
2. Set production-like environment variables, especially:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `JWT_ISSUER`
   - `JWT_AUDIENCE`
   - `REDIS_URL` if you want shared enrichment caching
3. Start the backend API.
4. If you enable hybrid scoring, set `ENABLE_ML_FRAUD_SCORING=1` intentionally.

## Benchmark Command

```bash
cd backend
venv\Scripts\python.exe scripts\load_test_check_fraud.py --base-url http://127.0.0.1:8001 --requests 200 --concurrency 20 --warmup 20
```

## Optional Existing Auth

If you want to benchmark with an existing token instead of letting the script create a benchmark user:

```bash
venv\Scripts\python.exe scripts\load_test_check_fraud.py ^
  --base-url http://127.0.0.1:8001 ^
  --access-token YOUR_TOKEN ^
  --user-id 1 ^
  --organisation-id 1 ^
  --requests 200 ^
  --concurrency 20
```

## Pass Criteria

- `success_rate` stays close to `100%`
- `latency_ms.p95` stays below your target SLA
- `status_codes` does not show unexpected `401`, `403`, `429`, or `500` spikes
- `GET /metrics` reflects the benchmark traffic

## Follow-Up

- Run the same script against staging and production-like infrastructure
- Capture benchmark output alongside deploy artifacts
- Add external metrics scraping and dashboards if you need long-term latency monitoring
