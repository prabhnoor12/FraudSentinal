from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import random
import statistics
import string
import time
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:8001"


def _random_suffix(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict]:
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **(headers or {}),
    }
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers=request_headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}
    except (urllib.error.URLError, TimeoutError) as exc:
        return 0, {"detail": str(exc), "error_type": type(exc).__name__}


def bootstrap_user(base_url: str, *, password: str, timeout: float) -> tuple[str, dict]:
    suffix = _random_suffix()
    email = f"loadtest_{suffix}@example.com"
    organisation_name = f"LoadTest_{suffix}"
    register_payload = {
        "email": email,
        "password": password,
        "organisation_name": organisation_name,
    }
    register_status, register_body = _request_json(
        "POST",
        f"{base_url}/auth/register",
        payload=register_payload,
        timeout=timeout,
    )
    if register_status not in {200, 201}:
        raise RuntimeError(f"Failed to register benchmark user: {register_status} {register_body}")

    login_status, login_body = _request_json(
        "POST",
        f"{base_url}/auth/login",
        payload={"email": email, "password": password},
        timeout=timeout,
    )
    if login_status != 200 or not login_body.get("access_token"):
        raise RuntimeError(f"Failed to login benchmark user: {login_status} {login_body}")

    me_status, me_body = _request_json(
        "GET",
        f"{base_url}/auth/me",
        headers={"Authorization": f"Bearer {login_body['access_token']}"},
        timeout=timeout,
    )
    if me_status != 200:
        raise RuntimeError(f"Failed to fetch benchmark user info: {me_status} {me_body}")

    return login_body["access_token"], me_body


def build_payload(
    *,
    user_id: int,
    organisation_id: int,
    request_index: int,
) -> dict:
    customer_bucket = request_index % 25
    amount = 50 + (request_index % 20) * 15
    return {
        "user_id": user_id,
        "organisation_id": organisation_id,
        "amount": float(amount),
        "currency": "USD",
        "payment_method": "cc" if request_index % 5 else "prepaid_card",
        "channel": "web",
        "customer_id": f"bench-customer-{customer_bucket}",
        "customer_email": f"bench{customer_bucket}@example.com",
        "billing_country": "US",
        "ip_address": f"10.0.{request_index % 10}.{(request_index % 200) + 1}",
        "device_id": f"bench-device-{request_index % 40}",
        "transactions_last_24h": request_index % 12,
        "failed_attempts_last_24h": request_index % 3,
        "metadata": {
            "screen_resolution": "1920x1080",
            "timezone": "UTC",
            "accept_language": "en-US",
            "accept_encoding": "gzip",
        },
    }


def run_single_request(
    *,
    base_url: str,
    token: str,
    payload: dict,
    timeout: float,
) -> dict:
    started_at = time.perf_counter()
    status, body = _request_json(
        "POST",
        f"{base_url}/check-fraud",
        payload=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "FraudSentinalLoadTest/1.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip",
        },
        timeout=timeout,
    )
    duration_ms = (time.perf_counter() - started_at) * 1000
    return {
        "status_code": status,
        "duration_ms": duration_ms,
        "body": body,
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (rank - lower)


def benchmark(
    *,
    base_url: str,
    token: str,
    user_id: int,
    organisation_id: int,
    total_requests: int,
    concurrency: int,
    warmup_requests: int,
    timeout: float,
) -> dict:
    warmup_results = []
    for index in range(warmup_requests):
        warmup_results.append(
            run_single_request(
                base_url=base_url,
                token=token,
                payload=build_payload(
                    user_id=user_id,
                    organisation_id=organisation_id,
                    request_index=index,
                ),
                timeout=timeout,
            )
        )

    started_at = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                run_single_request,
                base_url=base_url,
                token=token,
                payload=build_payload(
                    user_id=user_id,
                    organisation_id=organisation_id,
                    request_index=warmup_requests + index,
                ),
                timeout=timeout,
            )
            for index in range(total_requests)
        ]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed_seconds = time.perf_counter() - started_at

    durations = sorted(result["duration_ms"] for result in results)
    success_results = [result for result in results if 200 <= result["status_code"] < 300]
    non_success = [result for result in results if not (200 <= result["status_code"] < 300)]
    success_rate = (len(success_results) / len(results) * 100) if results else 0.0
    requests_per_second = (len(results) / elapsed_seconds) if elapsed_seconds else 0.0

    return {
        "base_url": base_url,
        "total_requests": len(results),
        "warmup_requests": len(warmup_results),
        "concurrency": concurrency,
        "success_count": len(success_results),
        "failure_count": len(non_success),
        "success_rate": round(success_rate, 2),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "requests_per_second": round(requests_per_second, 2),
        "latency_ms": {
            "min": round(min(durations), 2) if durations else 0.0,
            "avg": round(statistics.mean(durations), 2) if durations else 0.0,
            "median": round(statistics.median(durations), 2) if durations else 0.0,
            "p95": round(percentile(durations, 0.95), 2) if durations else 0.0,
            "p99": round(percentile(durations, 0.99), 2) if durations else 0.0,
            "max": round(max(durations), 2) if durations else 0.0,
        },
        "status_codes": _summarize_status_codes(results),
        "sample_failure": non_success[0]["body"] if non_success else None,
    }


def _summarize_status_codes(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        code = str(result["status_code"])
        counts[code] = counts.get(code, 0) + 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the /check-fraud endpoint with concurrent authenticated requests.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base API URL.")
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Total benchmark requests to execute.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of worker threads sending requests.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Warmup requests executed before measurement.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--password",
        default="StrongPass123!",
        help="Password used if the script bootstraps its own benchmark user.",
    )
    parser.add_argument(
        "--access-token",
        default=None,
        help="Optional bearer token. If omitted, the script registers and logs in a benchmark user.",
    )
    parser.add_argument("--user-id", type=int, default=None, help="User ID for pre-created auth.")
    parser.add_argument(
        "--organisation-id",
        type=int,
        default=None,
        help="Organisation ID for pre-created auth.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final result as raw JSON only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.access_token:
        if args.user_id is None or args.organisation_id is None:
            raise SystemExit("--user-id and --organisation-id are required when --access-token is provided.")
        token = args.access_token
        user = {"id": args.user_id, "organisation_id": args.organisation_id}
    else:
        token, user = bootstrap_user(
            args.base_url.rstrip("/"),
            password=args.password,
            timeout=args.timeout,
        )

    summary = benchmark(
        base_url=args.base_url.rstrip("/"),
        token=token,
        user_id=int(user["id"]),
        organisation_id=int(user["organisation_id"]),
        total_requests=args.requests,
        concurrency=args.concurrency,
        warmup_requests=args.warmup,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("FraudSentinal /check-fraud benchmark")
    print(f"base_url: {summary['base_url']}")
    print(f"requests: {summary['total_requests']}  warmup: {summary['warmup_requests']}  concurrency: {summary['concurrency']}")
    print(f"success_rate: {summary['success_rate']}%  rps: {summary['requests_per_second']}  elapsed_s: {summary['elapsed_seconds']}")
    print("latency_ms:")
    for key, value in summary["latency_ms"].items():
        print(f"  {key}: {value}")
    print(f"status_codes: {summary['status_codes']}")
    if summary["sample_failure"] is not None:
        print(f"sample_failure: {json.dumps(summary['sample_failure'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
