from __future__ import annotations

from collections import deque
from threading import Lock


class FraudMetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._decision_counts = {
            "approve": 0,
            "review": 0,
            "decline": 0,
        }
        self._recent_durations_ms: deque[float] = deque(maxlen=200)
        self._recent_risk_scores: deque[float] = deque(maxlen=200)

    def record_check(self, *, decision: str, risk_score: float, duration_ms: float) -> None:
        with self._lock:
            self._decision_counts.setdefault(decision, 0)
            self._decision_counts[decision] += 1
            self._recent_durations_ms.append(float(duration_ms))
            self._recent_risk_scores.append(float(risk_score))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            durations = list(self._recent_durations_ms)
            risk_scores = list(self._recent_risk_scores)
            total_checks = sum(self._decision_counts.values())

        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        avg_risk_score = (
            round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0
        )
        return {
            "fraud_checks_total": total_checks,
            "decision_counts": dict(self._decision_counts),
            "avg_duration_ms": avg_duration,
            "avg_risk_score": avg_risk_score,
            "recent_sample_size": len(durations),
        }

    def reset(self) -> None:
        with self._lock:
            for key in list(self._decision_counts.keys()):
                self._decision_counts[key] = 0
            self._recent_durations_ms.clear()
            self._recent_risk_scores.clear()


fraud_metrics = FraudMetricsStore()
