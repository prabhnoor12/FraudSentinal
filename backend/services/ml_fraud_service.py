from __future__ import annotations

import hashlib
import json
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
    "unique_devices_24hour",
    "unique_payment_methods_24hour",
    "unique_billing_countries_24hour",
    "unique_shipping_countries_24hour",
    "new_device",
    "device_fingerprint_confidence",
    "bin_confidence",
    "ip_geo_confidence",
]

MODEL_VERSION = "heuristic-v2"
DEFAULT_RULE_WEIGHT = 0.4
DEFAULT_ML_WEIGHT = 0.6


def is_ml_scoring_enabled() -> bool:
    return os.getenv("ENABLE_ML_FRAUD_SCORING", "").lower() in {"1", "true", "yes"}


def _coerce_float(
    transaction_data: dict[str, Any],
    key: str,
    *,
    default: float = 0.0,
) -> tuple[float, bool, bool]:
    """Return a float value plus diagnostics.

    Returns:
        value, used_default, was_invalid
    """
    raw_value = transaction_data.get(key, None)
    if raw_value is None or raw_value == "":
        return default, True, False
    try:
        return float(raw_value), False, False
    except (TypeError, ValueError):
        return default, True, True


def _coerce_bool(transaction_data: dict[str, Any], key: str) -> tuple[float, bool, bool]:
    raw_value = transaction_data.get(key, None)
    if raw_value is None or raw_value == "":
        return 0.0, True, False
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return 1.0, False, False
        if normalized in {"0", "false", "no", "n", "off"}:
            return 0.0, False, False
    return (1.0 if bool(raw_value) else 0.0), False, False


def extract_features(transaction_data: dict[str, Any]) -> dict[str, float]:
    features, _ = extract_features_with_diagnostics(transaction_data)
    return features


def extract_features_with_diagnostics(
    transaction_data: dict[str, Any],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    features: dict[str, float] = {}
    missing_features: list[str] = []
    defaulted_features: list[str] = []
    invalid_features: list[str] = []

    float_fields = (
        "amount",
        "transactions_last_24h",
        "failed_attempts_last_24h",
        "account_age_days",
        "bin_risk_score",
        "tx_count_1hour",
        "unique_ips_24hour",
        "unique_devices_24hour",
        "unique_payment_methods_24hour",
        "unique_billing_countries_24hour",
        "unique_shipping_countries_24hour",
        "device_fingerprint_confidence",
        "bin_confidence",
        "ip_geo_confidence",
    )
    bool_fields = ("ip_billing_country_mismatch", "is_prepaid", "new_device")

    for key in float_fields:
        value, used_default, was_invalid = _coerce_float(transaction_data, key)
        features[key] = value
        if used_default:
            defaulted_features.append(key)
        if was_invalid:
            invalid_features.append(key)
        if key not in transaction_data or transaction_data.get(key) in {None, ""}:
            missing_features.append(key)

    for key in bool_fields:
        value, used_default, was_invalid = _coerce_bool(transaction_data, key)
        features[key] = value
        if used_default:
            defaulted_features.append(key)
        if was_invalid:
            invalid_features.append(key)
        if key not in transaction_data or transaction_data.get(key) in {None, ""}:
            missing_features.append(key)

    return features, {
        "missing_features": list(dict.fromkeys(missing_features)),
        "defaulted_features": list(dict.fromkeys(defaulted_features)),
        "invalid_features": list(dict.fromkeys(invalid_features)),
    }


def _build_feature_contributions(features: dict[str, float]) -> list[dict[str, float | str | bool]]:
    return [
        {
            "feature": "amount",
            "contribution": round(min(features["amount"] / 50.0, 20.0), 2),
            "raw_value": features["amount"],
            "capped": features["amount"] / 50.0 > 20.0,
        },
        {
            "feature": "transactions_last_24h",
            "contribution": round(min(features["transactions_last_24h"] * 3.0, 15.0), 2),
            "raw_value": features["transactions_last_24h"],
            "capped": features["transactions_last_24h"] * 3.0 > 15.0,
        },
        {
            "feature": "failed_attempts_last_24h",
            "contribution": round(
                min(features["failed_attempts_last_24h"] * 8.0, 15.0), 2
            ),
            "raw_value": features["failed_attempts_last_24h"],
            "capped": features["failed_attempts_last_24h"] * 8.0 > 15.0,
        },
        {
            "feature": "account_age_days",
            "contribution": 10.0
            if features["account_age_days"] and features["account_age_days"] < 7
            else 0.0,
            "raw_value": features["account_age_days"],
            "capped": False,
        },
        {
            "feature": "ip_billing_country_mismatch",
            "contribution": 12.0 if features["ip_billing_country_mismatch"] else 0.0,
            "raw_value": features["ip_billing_country_mismatch"],
            "capped": False,
        },
        {
            "feature": "is_prepaid",
            "contribution": 8.0 if features["is_prepaid"] else 0.0,
            "raw_value": features["is_prepaid"],
            "capped": False,
        },
        {
            "feature": "bin_risk_score",
            "contribution": round(min(features["bin_risk_score"] * 0.25, 10.0), 2),
            "raw_value": features["bin_risk_score"],
            "capped": features["bin_risk_score"] * 0.25 > 10.0,
        },
        {
            "feature": "tx_count_1hour",
            "contribution": round(min(features["tx_count_1hour"] * 4.0, 15.0), 2),
            "raw_value": features["tx_count_1hour"],
            "capped": features["tx_count_1hour"] * 4.0 > 15.0,
        },
        {
            "feature": "unique_ips_24hour",
            "contribution": round(min(features["unique_ips_24hour"] * 5.0, 10.0), 2),
            "raw_value": features["unique_ips_24hour"],
            "capped": features["unique_ips_24hour"] * 5.0 > 10.0,
        },
        {
            "feature": "unique_devices_24hour",
            "contribution": round(min(features["unique_devices_24hour"] * 4.0, 10.0), 2),
            "raw_value": features["unique_devices_24hour"],
            "capped": features["unique_devices_24hour"] * 4.0 > 10.0,
        },
        {
            "feature": "unique_payment_methods_24hour",
            "contribution": round(
                min(features["unique_payment_methods_24hour"] * 4.0, 8.0), 2
            ),
            "raw_value": features["unique_payment_methods_24hour"],
            "capped": features["unique_payment_methods_24hour"] * 4.0 > 8.0,
        },
        {
            "feature": "unique_billing_countries_24hour",
            "contribution": round(
                min(features["unique_billing_countries_24hour"] * 6.0, 10.0), 2
            ),
            "raw_value": features["unique_billing_countries_24hour"],
            "capped": features["unique_billing_countries_24hour"] * 6.0 > 10.0,
        },
        {
            "feature": "unique_shipping_countries_24hour",
            "contribution": round(
                min(features["unique_shipping_countries_24hour"] * 6.0, 10.0), 2
            ),
            "raw_value": features["unique_shipping_countries_24hour"],
            "capped": features["unique_shipping_countries_24hour"] * 6.0 > 10.0,
        },
        {
            "feature": "new_device",
            "contribution": 15.0 if features["new_device"] else 0.0,
            "raw_value": features["new_device"],
            "capped": False,
        },
        {
            "feature": "device_fingerprint_confidence",
            "contribution": round(
                min((1.0 - features["device_fingerprint_confidence"]) * 10.0, 5.0),
                2,
            ),
            "raw_value": features["device_fingerprint_confidence"],
            "capped": False,
        },
        {
            "feature": "bin_confidence",
            "contribution": round(min((1.0 - features["bin_confidence"]) * 8.0, 4.0), 2),
            "raw_value": features["bin_confidence"],
            "capped": False,
        },
        {
            "feature": "ip_geo_confidence",
            "contribution": round(
                min((1.0 - features["ip_geo_confidence"]) * 8.0, 4.0), 2
            ),
            "raw_value": features["ip_geo_confidence"],
            "capped": False,
        },
    ]


def _hash_model_inputs(features: dict[str, float]) -> str:
    payload = json.dumps(features, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _blend_weights() -> tuple[float, float]:
    try:
        rule_weight = float(os.getenv("FRAUD_RULE_BLEND_WEIGHT", DEFAULT_RULE_WEIGHT))
    except (TypeError, ValueError):
        rule_weight = DEFAULT_RULE_WEIGHT
    try:
        ml_weight = float(os.getenv("FRAUD_ML_BLEND_WEIGHT", DEFAULT_ML_WEIGHT))
    except (TypeError, ValueError):
        ml_weight = DEFAULT_ML_WEIGHT
    total = rule_weight + ml_weight
    if total <= 0:
        return DEFAULT_RULE_WEIGHT, DEFAULT_ML_WEIGHT
    return round(rule_weight / total, 4), round(ml_weight / total, 4)


def predict(transaction_data: dict[str, Any]) -> dict[str, Any]:
    """Deterministic model-like scorer until a trained model is available."""
    features, diagnostics = extract_features_with_diagnostics(transaction_data)
    contributions = _build_feature_contributions(features)
    weighted_score = round(sum(item["contribution"] for item in contributions), 2)
    risk_score = min(weighted_score, 100.0)
    fraud_probability = round(max(min(risk_score / 100.0, 1.0), 0.0), 4)
    confidence = round(abs(fraud_probability - 0.5) * 2, 4)
    rule_weight, ml_weight = _blend_weights()

    return {
        "fraud_probability": fraud_probability,
        "risk_score": risk_score,
        "confidence": confidence,
        "model_version": MODEL_VERSION,
        "model_hash": _hash_model_inputs(features),
        "feature_count": len(features),
        "feature_contributions": contributions,
        "feature_diagnostics": diagnostics,
        "blend_weights": {
            "rule_weight": rule_weight,
            "ml_weight": ml_weight,
        },
    }


def combine_scores(
    rule_score: float,
    ml_score: float,
    *,
    rule_weight: float | None = None,
    ml_weight: float | None = None,
) -> float:
    """Blend the rule and ML scores with configurable weights."""
    normalized_rule_weight, normalized_ml_weight = _blend_weights()
    rule_weight = normalized_rule_weight if rule_weight is None else float(rule_weight)
    ml_weight = normalized_ml_weight if ml_weight is None else float(ml_weight)
    total = rule_weight + ml_weight
    if total <= 0:
        rule_weight, ml_weight = DEFAULT_RULE_WEIGHT, DEFAULT_ML_WEIGHT
        total = rule_weight + ml_weight
    blended = ((rule_score * rule_weight) + (ml_score * ml_weight)) / total
    return round(min(max(blended, 0.0), 100.0), 2)
