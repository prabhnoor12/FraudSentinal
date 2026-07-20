from __future__ import annotations

import os
from typing import Any


FEATURE_COLUMNS = [
    "amount",
    "transactions_last_24h",
    "failed_attempts_last_24h",
    "account_age_days",
    "ip_billing_country_mismatch",
    "is_prepaid",
    "bin_risk_score",
    "tx_count_1hour",
    "unique_ips_24hour",
    "new_device",
]


def is_ml_scoring_enabled() -> bool:
    return os.getenv("ENABLE_ML_FRAUD_SCORING", "").lower() in {"1", "true", "yes"}


def extract_features(transaction_data: dict[str, Any]) -> dict[str, float]:
    return {
        "amount": float(transaction_data.get("amount", 0) or 0),
        "transactions_last_24h": float(
            transaction_data.get("transactions_last_24h", 0) or 0
        ),
        "failed_attempts_last_24h": float(
            transaction_data.get("failed_attempts_last_24h", 0) or 0
        ),
        "account_age_days": float(transaction_data.get("account_age_days", 0) or 0),
        "ip_billing_country_mismatch": 1.0
        if transaction_data.get("ip_billing_country_mismatch")
        else 0.0,
        "is_prepaid": 1.0 if transaction_data.get("is_prepaid") else 0.0,
        "bin_risk_score": float(transaction_data.get("bin_risk_score", 0) or 0),
        "tx_count_1hour": float(transaction_data.get("tx_count_1hour", 0) or 0),
        "unique_ips_24hour": float(transaction_data.get("unique_ips_24hour", 0) or 0),
        "new_device": 1.0 if transaction_data.get("new_device") else 0.0,
    }


def predict(transaction_data: dict[str, Any]) -> dict[str, float | str]:
    """Deterministic model-like scorer until a trained model is available."""
    features = extract_features(transaction_data)

    weighted_score = 0.0
    weighted_score += min(features["amount"] / 50.0, 20.0)
    weighted_score += min(features["transactions_last_24h"] * 3.0, 15.0)
    weighted_score += min(features["failed_attempts_last_24h"] * 8.0, 15.0)
    weighted_score += 10.0 if features["account_age_days"] and features["account_age_days"] < 7 else 0.0
    weighted_score += 12.0 if features["ip_billing_country_mismatch"] else 0.0
    weighted_score += 8.0 if features["is_prepaid"] else 0.0
    weighted_score += min(features["bin_risk_score"] * 0.25, 10.0)
    weighted_score += min(features["tx_count_1hour"] * 4.0, 15.0)
    weighted_score += min(features["unique_ips_24hour"] * 5.0, 10.0)
    weighted_score += 15.0 if features["new_device"] else 0.0

    risk_score = min(round(weighted_score, 2), 100.0)
    fraud_probability = round(risk_score / 100.0, 4)
    confidence = round(abs(fraud_probability - 0.5) * 2, 4)

    return {
        "fraud_probability": fraud_probability,
        "risk_score": risk_score,
        "confidence": confidence,
        "model_version": "heuristic-v1",
    }


def combine_scores(rule_score: float, ml_score: float) -> float:
    return round((rule_score * 0.4) + (ml_score * 0.6), 2)
