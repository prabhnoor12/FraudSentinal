from __future__ import annotations

import asyncio
import json
from collections import Counter, deque
from threading import Lock
from typing import Any

from redis import RedisClient, get_redis_url


METRICS_NAMESPACE = "fraudsentinel:metrics"
RECENT_SAMPLE_LIMIT = 500


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 2)

    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    interpolated = ordered[lower] * (1 - weight) + ordered[upper] * weight
    return round(interpolated, 2)


def _run_redis_call(coro_factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())
    raise RuntimeError("Blocking Redis metrics helper cannot run inside an active loop")


def _decode_hash(payload: object) -> dict[str, str]:
    if not payload:
        return {}
    if isinstance(payload, dict):
        return {str(key): str(value) for key, value in payload.items()}
    if isinstance(payload, list):
        decoded: dict[str, str] = {}
        for index in range(0, len(payload), 2):
            if index + 1 >= len(payload):
                break
            decoded[str(payload[index])] = str(payload[index + 1])
        return decoded
    return {}


def _decode_recent_checks(payload: object) -> list[dict[str, Any]]:
    if not payload:
        return []
    if not isinstance(payload, list):
        return []

    decoded: list[dict[str, Any]] = []
    for item in payload:
        if not item:
            continue
        try:
            decoded.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return decoded


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class FraudMetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._decision_counts = {
            "approve": 0,
            "review": 0,
            "decline": 0,
        }
        self._recent_checks: deque[dict[str, Any]] = deque(maxlen=RECENT_SAMPLE_LIMIT)
        self._error_counts: Counter[str] = Counter()
        self._reason_code_counts: Counter[str] = Counter()
        self._threshold_source_counts: Counter[str] = Counter()
        self._matched_rule_counts: Counter[str] = Counter()
        self._rule_score_checks = 0
        self._ml_score_checks = 0
        self._ml_enabled_checks = 0
        self._degraded_checks = 0
        self._redis_client: RedisClient | None = None
        self._redis_url: str | None = None

    def _get_redis_client(self) -> RedisClient | None:
        redis_url = get_redis_url()
        if not redis_url:
            return None

        with self._lock:
            if self._redis_client and self._redis_url == redis_url:
                return self._redis_client
            self._redis_url = redis_url
            self._redis_client = RedisClient(redis_url)
            return self._redis_client

    def _record_local_check(
        self,
        *,
        decision: str,
        risk_score: float,
        duration_ms: float,
        rule_score: float | None = None,
        ml_score: float | None = None,
        ml_enabled: bool = False,
        degraded: bool = False,
        matched_rules: int | None = None,
        matched_rule_codes: list[str] | None = None,
        reason_codes: list[str] | None = None,
        threshold_source: str | None = None,
    ) -> None:
        self._decision_counts.setdefault(decision, 0)
        self._decision_counts[decision] += 1
        self._recent_checks.append(
            {
                "decision": decision,
                "risk_score": float(risk_score),
                "duration_ms": float(duration_ms),
                "rule_score": None if rule_score is None else float(rule_score),
                "ml_score": None if ml_score is None else float(ml_score),
                "ml_enabled": bool(ml_enabled),
                "degraded": bool(degraded),
                "matched_rules": matched_rules,
                "matched_rule_codes": matched_rule_codes or [],
                "reason_codes": reason_codes or [],
                "threshold_source": threshold_source,
            }
        )
        if matched_rule_codes:
            self._matched_rule_counts.update(matched_rule_codes)
        if reason_codes:
            self._reason_code_counts.update(reason_codes)
        if threshold_source:
            self._threshold_source_counts[threshold_source] += 1
        if rule_score is not None:
            self._rule_score_checks += 1
        if ml_score is not None:
            self._ml_score_checks += 1
        if ml_enabled:
            self._ml_enabled_checks += 1
        if degraded:
            self._degraded_checks += 1

    def record_check(
        self,
        *,
        decision: str,
        risk_score: float,
        duration_ms: float,
        rule_score: float | None = None,
        ml_score: float | None = None,
        ml_enabled: bool = False,
        degraded: bool = False,
        matched_rules: int | None = None,
        matched_rule_codes: list[str] | None = None,
        reason_codes: list[str] | None = None,
        threshold_source: str | None = None,
    ) -> None:
        with self._lock:
            self._record_local_check(
                decision=decision,
                risk_score=risk_score,
                duration_ms=duration_ms,
                rule_score=rule_score,
                ml_score=ml_score,
                ml_enabled=ml_enabled,
                degraded=degraded,
                matched_rules=matched_rules,
                matched_rule_codes=matched_rule_codes,
                reason_codes=reason_codes,
                threshold_source=threshold_source,
            )

        redis_client = self._get_redis_client()
        if redis_client is None:
            return

        payload = json.dumps(
            {
                "decision": decision,
                "risk_score": float(risk_score),
                "duration_ms": float(duration_ms),
                "rule_score": None if rule_score is None else float(rule_score),
                "ml_score": None if ml_score is None else float(ml_score),
                "ml_enabled": bool(ml_enabled),
                "degraded": bool(degraded),
                "matched_rules": matched_rules,
                "matched_rule_codes": matched_rule_codes or [],
                "reason_codes": reason_codes or [],
                "threshold_source": threshold_source,
            },
            default=str,
            sort_keys=True,
        )

        try:
            _run_redis_call(lambda: redis_client.execute("HINCRBY", f"{METRICS_NAMESPACE}:totals", "fraud_checks_total", 1))
            _run_redis_call(lambda: redis_client.execute("HINCRBY", f"{METRICS_NAMESPACE}:decision_counts", decision, 1))
            _run_redis_call(lambda: redis_client.execute("HINCRBYFLOAT", f"{METRICS_NAMESPACE}:sums", "risk_score", float(risk_score)))
            _run_redis_call(lambda: redis_client.execute("HINCRBYFLOAT", f"{METRICS_NAMESPACE}:sums", "duration_ms", float(duration_ms)))
            if rule_score is not None:
                _run_redis_call(lambda: redis_client.execute("HINCRBYFLOAT", f"{METRICS_NAMESPACE}:sums", "rule_score", float(rule_score)))
                _run_redis_call(lambda: redis_client.execute("HINCRBY", f"{METRICS_NAMESPACE}:totals", "rule_score_checks", 1))
            if ml_score is not None:
                _run_redis_call(lambda: redis_client.execute("HINCRBYFLOAT", f"{METRICS_NAMESPACE}:sums", "ml_score", float(ml_score)))
                _run_redis_call(lambda: redis_client.execute("HINCRBY", f"{METRICS_NAMESPACE}:totals", "ml_score_checks", 1))
            if ml_enabled:
                _run_redis_call(lambda: redis_client.execute("HINCRBY", f"{METRICS_NAMESPACE}:totals", "ml_enabled_checks", 1))
            if degraded:
                _run_redis_call(lambda: redis_client.execute("HINCRBY", f"{METRICS_NAMESPACE}:totals", "degraded_checks", 1))
            for reason_code in reason_codes or []:
                _run_redis_call(
                    lambda: redis_client.execute(
                        "HINCRBY",
                        f"{METRICS_NAMESPACE}:reason_code_counts",
                        reason_code,
                        1,
                    )
                )
            if threshold_source:
                _run_redis_call(
                    lambda: redis_client.execute(
                        "HINCRBY",
                        f"{METRICS_NAMESPACE}:threshold_source_counts",
                        threshold_source,
                        1,
                    )
                )
            for rule_code in matched_rule_codes or []:
                _run_redis_call(
                    lambda: redis_client.execute(
                        "HINCRBY",
                        f"{METRICS_NAMESPACE}:matched_rule_counts",
                        rule_code,
                        1,
                    )
                )
            _run_redis_call(lambda: redis_client.execute("LPUSH", f"{METRICS_NAMESPACE}:recent_checks", payload))
            _run_redis_call(lambda: redis_client.execute("LTRIM", f"{METRICS_NAMESPACE}:recent_checks", 0, RECENT_SAMPLE_LIMIT - 1))
        except Exception:
            return

    def record_error(self, error_type: str) -> None:
        with self._lock:
            self._error_counts[error_type] += 1

        redis_client = self._get_redis_client()
        if redis_client is None:
            return

        try:
            _run_redis_call(
                lambda: redis_client.execute(
                    "HINCRBY",
                    f"{METRICS_NAMESPACE}:error_counts",
                    error_type,
                    1,
                )
            )
        except Exception:
            return

    def _snapshot_from_local(self) -> dict[str, object]:
        with self._lock:
            recent_checks = list(self._recent_checks)
            decision_counts = dict(self._decision_counts)
            error_counts = dict(self._error_counts)
            reason_code_counts = dict(self._reason_code_counts)
            threshold_source_counts = dict(self._threshold_source_counts)
            matched_rule_counts = dict(self._matched_rule_counts)
            rule_score_checks = self._rule_score_checks
            ml_score_checks = self._ml_score_checks
            ml_enabled_checks = self._ml_enabled_checks
            degraded_checks = self._degraded_checks

        return self._build_snapshot(
            recent_checks=recent_checks,
            decision_counts=decision_counts,
            error_counts=error_counts,
            reason_code_counts=reason_code_counts,
            threshold_source_counts=threshold_source_counts,
            matched_rule_counts=matched_rule_counts,
            rule_score_checks=rule_score_checks,
            ml_score_checks=ml_score_checks,
            ml_enabled_checks=ml_enabled_checks,
            degraded_checks=degraded_checks,
            backend="memory",
        )

    def _snapshot_from_redis(self) -> dict[str, object] | None:
        redis_client = self._get_redis_client()
        if redis_client is None:
            return None

        try:
            totals = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:totals")))
            decision_counts = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:decision_counts")))
            sums = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:sums")))
            error_counts = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:error_counts")))
            reason_code_counts = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:reason_code_counts")))
            threshold_source_counts = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:threshold_source_counts")))
            matched_rule_counts = _decode_hash(_run_redis_call(lambda: redis_client.execute("HGETALL", f"{METRICS_NAMESPACE}:matched_rule_counts")))
            recent_checks = _decode_recent_checks(
                _run_redis_call(
                    lambda: redis_client.execute(
                        "LRANGE",
                        f"{METRICS_NAMESPACE}:recent_checks",
                        0,
                        RECENT_SAMPLE_LIMIT - 1,
                    )
                )
            )
        except Exception:
            return None

        return self._build_snapshot(
            recent_checks=recent_checks,
            decision_counts={key: _safe_int(value) for key, value in decision_counts.items()},
            error_counts={key: _safe_int(value) for key, value in error_counts.items()},
            reason_code_counts={key: _safe_int(value) for key, value in reason_code_counts.items()},
            threshold_source_counts={key: _safe_int(value) for key, value in threshold_source_counts.items()},
            matched_rule_counts={key: _safe_int(value) for key, value in matched_rule_counts.items()},
            rule_score_checks=_safe_int(totals.get("rule_score_checks", 0)),
            ml_score_checks=_safe_int(totals.get("ml_score_checks", 0)),
            ml_enabled_checks=_safe_int(totals.get("ml_enabled_checks", 0)),
            degraded_checks=_safe_int(totals.get("degraded_checks", 0)),
            backend="redis",
            totals=totals,
            sums=sums,
        )

    def _build_snapshot(
        self,
        *,
        recent_checks: list[dict[str, Any]],
        decision_counts: dict[str, int],
        error_counts: dict[str, int],
        reason_code_counts: dict[str, int],
        threshold_source_counts: dict[str, int],
        matched_rule_counts: dict[str, int],
        rule_score_checks: int,
        ml_score_checks: int,
        ml_enabled_checks: int,
        degraded_checks: int,
        backend: str,
        totals: dict[str, str] | None = None,
        sums: dict[str, str] | None = None,
    ) -> dict[str, object]:
        durations = [float(check.get("duration_ms", 0.0)) for check in recent_checks]
        risk_scores = [float(check.get("risk_score", 0.0)) for check in recent_checks]
        rule_scores = [
            float(check["rule_score"])
            for check in recent_checks
            if check.get("rule_score") is not None
        ]
        ml_scores = [
            float(check["ml_score"])
            for check in recent_checks
            if check.get("ml_score") is not None
        ]
        total_checks = sum(decision_counts.values())
        recent_sample_size = len(recent_checks)

        if sums:
            avg_duration = round(_safe_float(sums.get("duration_ms")) / max(total_checks, 1), 2)
            avg_risk_score = round(_safe_float(sums.get("risk_score")) / max(total_checks, 1), 2)
            avg_rule_score = round(_safe_float(sums.get("rule_score")) / max(rule_score_checks, 1), 2) if rule_score_checks else 0.0
            avg_ml_score = round(_safe_float(sums.get("ml_score")) / max(ml_score_checks, 1), 2) if ml_score_checks else 0.0
        else:
            avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
            avg_risk_score = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0
            avg_rule_score = round(sum(rule_scores) / len(rule_scores), 2) if rule_scores else 0.0
            avg_ml_score = round(sum(ml_scores) / len(ml_scores), 2) if ml_scores else 0.0

        return {
            "backend": backend,
            "fraud_checks_total": total_checks,
            "decision_counts": {
                "approve": decision_counts.get("approve", 0),
                "review": decision_counts.get("review", 0),
                "decline": decision_counts.get("decline", 0),
            },
            "avg_duration_ms": avg_duration,
            "avg_risk_score": avg_risk_score,
            "avg_rule_score": avg_rule_score,
            "avg_ml_score": avg_ml_score,
            "duration_p50_ms": _percentile(durations, 0.5),
            "duration_p95_ms": _percentile(durations, 0.95),
            "duration_p99_ms": _percentile(durations, 0.99),
            "risk_score_p50": _percentile(risk_scores, 0.5),
            "risk_score_p95": _percentile(risk_scores, 0.95),
            "risk_score_p99": _percentile(risk_scores, 0.99),
            "recent_sample_size": recent_sample_size,
            "ml_enabled_checks": ml_enabled_checks,
            "degraded_checks": degraded_checks,
            "error_counts": error_counts,
            "reason_code_counts": reason_code_counts,
            "threshold_source_counts": threshold_source_counts,
            "matched_rule_counts": matched_rule_counts,
            "rule_score_checks": rule_score_checks,
            "ml_score_checks": ml_score_checks,
        }

    def snapshot(self) -> dict[str, object]:
        redis_snapshot = self._snapshot_from_redis()
        if redis_snapshot is not None:
            return redis_snapshot
        return self._snapshot_from_local()

    def prometheus_text(self) -> str:
        snapshot = self.snapshot()
        decision_counts = snapshot["decision_counts"]
        error_counts = snapshot["error_counts"]

        lines = [
            "# HELP fraudsentinel_fraud_checks_total Total fraud checks processed.",
            "# TYPE fraudsentinel_fraud_checks_total counter",
            f'fraudsentinel_fraud_checks_total {snapshot["fraud_checks_total"]}',
            "# HELP fraudsentinel_fraud_check_decisions_total Total fraud check decisions by outcome.",
            "# TYPE fraudsentinel_fraud_check_decisions_total counter",
        ]

        for decision, count in decision_counts.items():
            lines.append(
                f'fraudsentinel_fraud_check_decisions_total{{decision="{decision}"}} {count}'
            )

        lines.extend(
            [
                "# HELP fraudsentinel_fraud_check_duration_ms Fraud check latency in milliseconds.",
                "# TYPE fraudsentinel_fraud_check_duration_ms gauge",
                f'fraudsentinel_fraud_check_duration_ms{{quantile="avg"}} {snapshot["avg_duration_ms"]}',
                f'fraudsentinel_fraud_check_duration_ms{{quantile="p50"}} {snapshot["duration_p50_ms"]}',
                f'fraudsentinel_fraud_check_duration_ms{{quantile="p95"}} {snapshot["duration_p95_ms"]}',
                f'fraudsentinel_fraud_check_duration_ms{{quantile="p99"}} {snapshot["duration_p99_ms"]}',
                "# HELP fraudsentinel_fraud_check_risk_score Fraud check risk score distribution.",
                "# TYPE fraudsentinel_fraud_check_risk_score gauge",
                f'fraudsentinel_fraud_check_risk_score{{quantile="avg"}} {snapshot["avg_risk_score"]}',
                f'fraudsentinel_fraud_check_risk_score{{quantile="p50"}} {snapshot["risk_score_p50"]}',
                f'fraudsentinel_fraud_check_risk_score{{quantile="p95"}} {snapshot["risk_score_p95"]}',
                f'fraudsentinel_fraud_check_risk_score{{quantile="p99"}} {snapshot["risk_score_p99"]}',
                "# HELP fraudsentinel_fraud_check_ml_enabled_total Fraud checks that used ML scoring.",
                "# TYPE fraudsentinel_fraud_check_ml_enabled_total counter",
                f'fraudsentinel_fraud_check_ml_enabled_total {snapshot["ml_enabled_checks"]}',
                "# HELP fraudsentinel_fraud_check_degraded_total Fraud checks completed with a degraded dependency.",
                "# TYPE fraudsentinel_fraud_check_degraded_total counter",
                f'fraudsentinel_fraud_check_degraded_total {snapshot["degraded_checks"]}',
                "# HELP fraudsentinel_fraud_check_errors_total Fraud check errors by type.",
                "# TYPE fraudsentinel_fraud_check_errors_total counter",
            ]
        )

        for error_type, count in error_counts.items():
            lines.append(
                f'fraudsentinel_fraud_check_errors_total{{type="{error_type}"}} {count}'
            )

        lines.append(
            f'fraudsentinel_fraud_metrics_backend_info{{backend="{snapshot["backend"]}"}} 1'
        )
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._decision_counts = {
                "approve": 0,
                "review": 0,
                "decline": 0,
            }
            self._recent_checks.clear()
            self._error_counts.clear()
            self._reason_code_counts.clear()
            self._threshold_source_counts.clear()
            self._matched_rule_counts.clear()
            self._rule_score_checks = 0
            self._ml_score_checks = 0
            self._ml_enabled_checks = 0
            self._degraded_checks = 0

        redis_client = self._get_redis_client()
        if redis_client is None:
            return

        try:
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:totals"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:decision_counts"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:sums"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:error_counts"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:reason_code_counts"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:threshold_source_counts"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:matched_rule_counts"))
            _run_redis_call(lambda: redis_client.execute("DEL", f"{METRICS_NAMESPACE}:recent_checks"))
        except Exception:
            return


fraud_metrics = FraudMetricsStore()
