from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from collections import defaultdict
from functools import lru_cache
from numbers import Real
from typing import Any

from sqlalchemy.orm import Session

from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.fraud_rule_schemas import FraudRuleOperator
from schemas.transaction_schemas import TransactionCreate
from services import (
    device_fingerprint_service,
    fraud_rule_service,
    ml_fraud_service,
    transaction_service,
    velocity_service,
)
from services.settings_service import get_settings_service
from utils.exception_handling_utils import NotFoundError


logger = logging.getLogger("fraudsentinel.scoring")

DEFAULT_REVIEW_THRESHOLD = 40.0
DEFAULT_DECLINE_THRESHOLD = 70.0
SCORING_VERSION = "hybrid-v2"


@dataclass(frozen=True)
class ScoreThresholds:
    review: float
    decline: float
    source: str


def _is_missing(value: Any) -> bool:
    return value in {None, ""} or value == [] or value == {}


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_value(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(item) for item in value))
    return value


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _coerce_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, Real):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _normalize_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip().lower()
    return None


def _normalize_collection(values: Any) -> set[Any] | None:
    if isinstance(values, (list, tuple, set)):
        normalized: set[Any] = set()
        for item in values:
            normalized.add(_normalize_text(item) if isinstance(item, str) else item)
        return normalized
    return None


def _matches_rule_values(
    operator: FraudRuleOperator,
    candidate: Any,
    comparison_value: Any,
    secondary_value: Any = None,
) -> bool:
    if operator == FraudRuleOperator.is_missing:
        return _is_missing(candidate)

    if operator == FraudRuleOperator.field_mismatch:
        if _is_missing(candidate) or _is_missing(secondary_value):
            return False
        candidate_text = _normalize_text(candidate)
        secondary_text = _normalize_text(secondary_value)
        if candidate_text is not None and secondary_text is not None:
            return candidate_text != secondary_text
        return candidate != secondary_value

    if _is_missing(candidate):
        return False

    if operator in {
        FraudRuleOperator.gte,
        FraudRuleOperator.gt,
        FraudRuleOperator.lte,
        FraudRuleOperator.lt,
    }:
        candidate_number = _coerce_numeric(candidate)
        comparison_number = _coerce_numeric(comparison_value)
        if candidate_number is None or comparison_number is None:
            return False
        if operator == FraudRuleOperator.gte:
            return candidate_number >= comparison_number
        if operator == FraudRuleOperator.gt:
            return candidate_number > comparison_number
        if operator == FraudRuleOperator.lte:
            return candidate_number <= comparison_number
        return candidate_number < comparison_number

    if operator == FraudRuleOperator.eq:
        candidate_number = _coerce_numeric(candidate)
        comparison_number = _coerce_numeric(comparison_value)
        if candidate_number is not None and comparison_number is not None:
            return candidate_number == comparison_number
        candidate_text = _normalize_text(candidate)
        comparison_text = _normalize_text(comparison_value)
        if candidate_text is not None and comparison_text is not None:
            return candidate_text == comparison_text
        return candidate == comparison_value

    if operator == FraudRuleOperator.neq:
        candidate_number = _coerce_numeric(candidate)
        comparison_number = _coerce_numeric(comparison_value)
        if candidate_number is not None and comparison_number is not None:
            return candidate_number != comparison_number
        candidate_text = _normalize_text(candidate)
        comparison_text = _normalize_text(comparison_value)
        if candidate_text is not None and comparison_text is not None:
            return candidate_text != comparison_text
        return candidate != comparison_value

    if operator == FraudRuleOperator.in_list:
        normalized_collection = _normalize_collection(comparison_value)
        if normalized_collection is None:
            return False
        candidate_text = _normalize_text(candidate)
        if candidate_text is not None:
            return candidate_text in normalized_collection
        return candidate in normalized_collection

    if operator == FraudRuleOperator.not_in:
        normalized_collection = _normalize_collection(comparison_value)
        if normalized_collection is None:
            return False
        candidate_text = _normalize_text(candidate)
        if candidate_text is not None:
            return candidate_text not in normalized_collection
        return candidate not in normalized_collection

    if operator == FraudRuleOperator.between:
        candidate_number = _coerce_numeric(candidate)
        if candidate_number is None:
            return False
        if not isinstance(comparison_value, (list, tuple)) or len(comparison_value) != 2:
            return False
        low = _coerce_numeric(comparison_value[0])
        high = _coerce_numeric(comparison_value[1])
        if low is None or high is None:
            return False
        return low <= candidate_number <= high

    if operator == FraudRuleOperator.contains:
        candidate_text = _normalize_text(candidate)
        if candidate_text is not None:
            comparison_text = _normalize_text(comparison_value)
            return comparison_text is not None and comparison_text in candidate_text
        normalized_collection = _normalize_collection(candidate)
        if normalized_collection is None:
            return False
        comparison_text = _normalize_text(comparison_value)
        if comparison_text is not None:
            return comparison_text in normalized_collection
        return comparison_value in normalized_collection

    if operator == FraudRuleOperator.starts_with:
        candidate_text = _normalize_text(candidate)
        comparison_text = _normalize_text(comparison_value)
        if candidate_text is None or comparison_text is None:
            return False
        return candidate_text.startswith(comparison_text)

    if operator == FraudRuleOperator.ends_with:
        candidate_text = _normalize_text(candidate)
        comparison_text = _normalize_text(comparison_value)
        if candidate_text is None or comparison_text is None:
            return False
        return candidate_text.endswith(comparison_text)

    if operator == FraudRuleOperator.regex:
        candidate_text = _normalize_text(candidate)
        if candidate_text is None or not isinstance(comparison_value, str):
            return False
        try:
            return re.search(comparison_value, candidate_text) is not None
        except re.error:
            return False

    return False


@lru_cache(maxsize=10000)
def _evaluate_rule_cached(
    operator_value: str,
    candidate: Any,
    comparison_value: Any,
    secondary_value: Any,
) -> bool:
    return _matches_rule_values(
        FraudRuleOperator(operator_value),
        candidate,
        comparison_value,
        secondary_value,
    )


def _matches_rule(rule, transaction_data: dict) -> bool:
    candidate = _freeze_value(transaction_data.get(rule.field_name))
    secondary_value = _freeze_value(
        transaction_data.get(rule.secondary_field_name)
        if rule.secondary_field_name
        else None
    )
    comparison_value = _freeze_value(rule.comparison_value)
    return _evaluate_rule_cached(
        _enum_value(rule.operator),
        candidate,
        comparison_value,
        secondary_value,
    )


def _build_rule_index(rules) -> dict[str, list]:
    rule_index: dict[str, list] = {}
    for rule in rules:
        rule_index.setdefault(rule.field_name, []).append(rule)
        if rule.secondary_field_name:
            rule_index.setdefault(rule.secondary_field_name, []).append(rule)
    return rule_index


def _get_relevant_rules(effective_rules, transaction_data: dict) -> list:
    rule_index = _build_rule_index(effective_rules)
    relevant_rules: dict[int, object] = {}

    for field_name in transaction_data.keys():
        for rule in rule_index.get(field_name, []):
            relevant_rules[rule.id] = rule

    for rule in effective_rules:
        if rule.operator in {
            FraudRuleOperator.is_missing,
            FraudRuleOperator.field_mismatch,
        }:
            relevant_rules[rule.id] = rule

    return sorted(
        relevant_rules.values(),
        key=lambda rule: (rule.priority, rule.id),
    )


def _serialize_rule(rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_code": rule.rule_code,
        "reason_code": _enum_value(rule.reason_code),
        "weight": rule.weight,
        "field_name": rule.field_name,
        "operator": _enum_value(rule.operator),
        "comparison_value": rule.comparison_value,
        "secondary_field_name": rule.secondary_field_name,
        "group_key": getattr(rule, "group_key", None),
        "group_cap": getattr(rule, "group_cap", None),
        "exclude_rule_codes": list(getattr(rule, "exclude_rule_codes", []) or []),
        "exclude_group_keys": list(getattr(rule, "exclude_group_keys", []) or []),
        "rule_version": getattr(rule, "rule_version", 1),
        "priority": rule.priority,
        "enabled": rule.enabled,
        "organisation_id": rule.organisation_id,
    }


def _fingerprint_rules(serialized_rules: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        serialized_rules,
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _coerce_threshold_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _extract_profile_override(
    profiles: dict[str, Any] | None,
    *,
    channel: str | None,
    transaction_type: str | None,
) -> dict[str, Any]:
    if not profiles:
        return {}

    override: dict[str, Any] = {}
    default_profile = profiles.get("default")
    if isinstance(default_profile, dict):
        override.update(default_profile)

    if channel:
        channel_profiles = profiles.get("channels")
        if isinstance(channel_profiles, dict):
            channel_profile = channel_profiles.get(channel)
            if isinstance(channel_profile, dict):
                override.update(channel_profile)

    if transaction_type:
        tx_profiles = profiles.get("transaction_types")
        if isinstance(tx_profiles, dict):
            tx_profile = tx_profiles.get(transaction_type)
            if isinstance(tx_profile, dict):
                override.update(tx_profile)

    combinations = profiles.get("combinations")
    if isinstance(combinations, dict) and (channel or transaction_type):
        combo_keys = []
        if channel and transaction_type:
            combo_keys.append(f"{channel}:{transaction_type}")
            combo_keys.append(f"{channel}|{transaction_type}")
        if channel:
            combo_keys.append(channel)
        if transaction_type:
            combo_keys.append(transaction_type)
        for key in combo_keys:
            combo_profile = combinations.get(key)
            if isinstance(combo_profile, dict):
                override.update(combo_profile)
                break

    return override


def _load_thresholds(
    db: Session,
    organisation_id: int | None,
    *,
    channel: str | None = None,
    transaction_type: str | None = None,
) -> tuple[ScoreThresholds, dict[str, Any]]:
    try:
        settings = get_settings_service(db, organisation_id)
    except NotFoundError:
        logger.info(
            "fraud_scoring_threshold_defaults",
            extra={"organisation_id": organisation_id},
        )
        return ScoreThresholds(
            review=DEFAULT_REVIEW_THRESHOLD,
            decline=DEFAULT_DECLINE_THRESHOLD,
            source="defaults",
        ), {
            "profile_key": f"tenant:{organisation_id or 'global'}|default",
            "profile_source": "defaults",
            "profile_overrides": {},
        }
    except Exception:
        logger.exception(
            "fraud_scoring_threshold_lookup_failed",
            extra={"organisation_id": organisation_id},
        )
        return ScoreThresholds(
            review=DEFAULT_REVIEW_THRESHOLD,
            decline=DEFAULT_DECLINE_THRESHOLD,
            source="fallback",
        ), {
            "profile_key": "fallback",
            "profile_source": "fallback",
            "profile_overrides": {},
        }

    profile_overrides = _extract_profile_override(
        getattr(settings, "threshold_profiles", None),
        channel=channel,
        transaction_type=transaction_type,
    )


def _safe_enrichment_lookup(db: Session, payload: TransactionCreate) -> tuple[dict[str, Any], list[str]]:
    from services.enrichment_service import get_enriched_transaction_data

    degradation_reasons: list[str] = []
    try:
        enrichment_data = get_enriched_transaction_data(
            db,
            ip_address=payload.ip_address if hasattr(payload, "ip_address") else None,
            card_number=payload.card_number if hasattr(payload, "card_number") else None,
            billing_country=payload.billing_country
            if hasattr(payload, "billing_country")
            else None,
        )
        return enrichment_data, degradation_reasons
    except Exception:
        logger.exception(
            "enrichment_lookup_failed",
            extra={"organisation_id": payload.organisation_id},
        )
        degradation_reasons.append("enrichment_lookup_failed")
        return {}, degradation_reasons
    review_threshold = _coerce_threshold_value(
        profile_overrides.get("review", settings.review_threshold),
        DEFAULT_REVIEW_THRESHOLD,
    )
    decline_threshold = _coerce_threshold_value(
        profile_overrides.get("decline", settings.decline_threshold),
        DEFAULT_DECLINE_THRESHOLD,
    )
    if decline_threshold < review_threshold:
        logger.warning(
            "fraud_scoring_thresholds_normalized",
            extra={
                "organisation_id": organisation_id,
                "review_threshold": review_threshold,
                "decline_threshold": decline_threshold,
            },
        )
        decline_threshold = review_threshold

    profile_key_parts = [f"tenant:{organisation_id or 'global'}"]
    if channel:
        profile_key_parts.append(f"channel:{channel}")
    if transaction_type:
        profile_key_parts.append(f"transaction_type:{transaction_type}")

    return ScoreThresholds(
        review=review_threshold,
        decline=decline_threshold,
        source="settings",
    ), {
        "profile_key": "|".join(profile_key_parts),
        "profile_source": "settings",
        "profile_overrides": profile_overrides,
    }


def _build_scoring_context(
    *,
    organisation_id: int | None,
    transaction_data: dict[str, Any],
    effective_rules,
    thresholds: ScoreThresholds,
    threshold_profile: dict[str, Any],
) -> dict[str, Any]:
    serialized_rules = [_serialize_rule(rule) for rule in effective_rules]
    rules_hash = _fingerprint_rules(serialized_rules)
    return {
        "organisation_id": organisation_id,
        "rules_version": f"ruleset-{rules_hash}",
        "rules_hash": rules_hash,
        "rules_count": len(serialized_rules),
        "rules": serialized_rules,
        "thresholds": {
            "review": thresholds.review,
            "decline": thresholds.decline,
            "source": thresholds.source,
        },
        "threshold_profile": threshold_profile,
        "scoring_version": SCORING_VERSION,
        "feature_columns": list(ml_fraud_service.FEATURE_COLUMNS),
        "evaluated_keys": sorted(transaction_data.keys()),
    }


@dataclass(frozen=True)
class SerializedRule:
    id: int
    name: str
    rule_code: str
    reason_code: ReasonCode
    weight: float
    field_name: str
    operator: FraudRuleOperator
    comparison_value: Any
    secondary_field_name: str | None
    group_key: str | None
    group_cap: float | None
    exclude_rule_codes: tuple[str, ...]
    exclude_group_keys: tuple[str, ...]
    rule_version: int
    priority: int
    enabled: bool
    organisation_id: int | None


def _deserialize_rule_snapshot(rule_data: dict[str, Any]) -> SerializedRule:
    return SerializedRule(
        id=int(rule_data["id"]),
        name=str(rule_data.get("name") or ""),
        rule_code=str(rule_data.get("rule_code") or ""),
        reason_code=ReasonCode(rule_data["reason_code"]),
        weight=float(rule_data["weight"]),
        field_name=str(rule_data["field_name"]),
        operator=FraudRuleOperator(rule_data["operator"]),
        comparison_value=rule_data.get("comparison_value"),
        secondary_field_name=rule_data.get("secondary_field_name"),
        group_key=rule_data.get("group_key"),
        group_cap=(
            float(rule_data["group_cap"])
            if rule_data.get("group_cap") is not None
            else None
        ),
        exclude_rule_codes=tuple(rule_data.get("exclude_rule_codes") or ()),
        exclude_group_keys=tuple(rule_data.get("exclude_group_keys") or ()),
        rule_version=int(rule_data.get("rule_version") or 1),
        priority=int(rule_data.get("priority") or 0),
        enabled=bool(rule_data.get("enabled", True)),
        organisation_id=rule_data.get("organisation_id"),
    )


def _build_group_caps(effective_rules) -> dict[str, float]:
    group_caps: dict[str, float] = {}
    for rule in effective_rules:
        group_key = getattr(rule, "group_key", None)
        group_cap = getattr(rule, "group_cap", None)
        if not group_key or group_cap is None:
            continue
        group_caps[group_key] = (
            min(group_caps[group_key], float(group_cap))
            if group_key in group_caps
            else float(group_cap)
        )
    return group_caps


def _score_with_rules(
    *,
    transaction_data: dict[str, Any],
    effective_rules,
    thresholds: ScoreThresholds,
    scoring_context: dict[str, Any],
    ml_enabled: bool,
) -> dict[str, Any]:
    group_caps = _build_group_caps(effective_rules)
    matched_rules = []
    reason_codes: list[ReasonCode] = []
    reason_code_totals: dict[str, float] = {}
    score_breakdown: list[dict[str, Any]] = []
    suppressed_rule_codes: set[str] = set()
    suppressed_group_keys: set[str] = set()
    suppression_counts: dict[str, int] = defaultdict(int)
    applied_group_totals: dict[str, float] = defaultdict(float)
    total_score = 0.0

    for rule in _get_relevant_rules(effective_rules, transaction_data):
        if rule.rule_code in suppressed_rule_codes:
            suppression_counts["rule_exclusion"] += 1
            score_breakdown.append(
                {
                    "source": "rule",
                    "rule_id": rule.id,
                    "rule_code": rule.rule_code,
                    "reason_code": _enum_value(rule.reason_code),
                    "field_name": str(rule.field_name),
                    "operator": _enum_value(rule.operator),
                    "matched_value": transaction_data.get(rule.field_name),
                    "comparison_value": rule.comparison_value,
                    "raw_weight": float(rule.weight),
                    "applied_weight": 0.0,
                    "group_key": getattr(rule, "group_key", None),
                    "group_cap": getattr(rule, "group_cap", None),
                    "group_capped": False,
                    "suppressed": True,
                    "suppression_reason": "rule_exclusion",
                }
            )
            continue
        if getattr(rule, "group_key", None) and rule.group_key in suppressed_group_keys:
            suppression_counts["group_exclusion"] += 1
            score_breakdown.append(
                {
                    "source": "rule",
                    "rule_id": rule.id,
                    "rule_code": rule.rule_code,
                    "reason_code": _enum_value(rule.reason_code),
                    "field_name": str(rule.field_name),
                    "operator": _enum_value(rule.operator),
                    "matched_value": transaction_data.get(rule.field_name),
                    "comparison_value": rule.comparison_value,
                    "raw_weight": float(rule.weight),
                    "applied_weight": 0.0,
                    "group_key": getattr(rule, "group_key", None),
                    "group_cap": getattr(rule, "group_cap", None),
                    "group_capped": False,
                    "suppressed": True,
                    "suppression_reason": "group_exclusion",
                }
            )
            continue
        if not _matches_rule(rule, transaction_data):
            continue

        rule_weight = float(rule.weight)
        applied_weight = rule_weight
        group_key = getattr(rule, "group_key", None)
        group_cap = group_caps.get(group_key) if group_key else None
        capped_by_group = False
        if group_key and group_cap is not None:
            remaining = max(group_cap - applied_group_totals[group_key], 0.0)
            applied_weight = min(applied_weight, remaining)
            capped_by_group = applied_weight < rule_weight
        if applied_weight <= 0:
            score_breakdown.append(
                {
                    "source": "rule",
                    "rule_id": rule.id,
                    "rule_code": rule.rule_code,
                    "reason_code": _enum_value(rule.reason_code),
                    "field_name": str(rule.field_name),
                    "operator": _enum_value(rule.operator),
                    "matched_value": transaction_data.get(rule.field_name),
                    "comparison_value": rule.comparison_value,
                    "raw_weight": rule_weight,
                    "applied_weight": 0.0,
                    "group_key": group_key,
                    "group_cap": group_cap,
                    "group_capped": True,
                    "suppressed": True,
                    "suppression_reason": "group_cap",
                }
            )
            continue

        matched_rules.append(rule)
        total_score += applied_weight
        if group_key:
            applied_group_totals[group_key] += applied_weight
        reason_code = ReasonCode(rule.reason_code)
        reason_code_totals[reason_code.value] = (
            reason_code_totals.get(reason_code.value, 0.0) + applied_weight
        )
        if reason_code not in reason_codes:
            reason_codes.append(reason_code)
        score_breakdown.append(
            {
                "source": "rule",
                "rule_id": rule.id,
                "rule_code": rule.rule_code,
                "rule_version": getattr(rule, "rule_version", 1),
                "reason_code": reason_code.value,
                "field_name": str(rule.field_name),
                "operator": _enum_value(rule.operator),
                "matched_value": transaction_data.get(rule.field_name),
                "comparison_value": rule.comparison_value,
                "raw_weight": rule_weight,
                "applied_weight": applied_weight,
                "group_key": group_key,
                "group_cap": group_cap,
                "group_total_after": (
                    applied_group_totals[group_key] if group_key else None
                ),
                "group_capped": capped_by_group,
                "exclude_rule_codes": list(getattr(rule, "exclude_rule_codes", []) or []),
                "exclude_group_keys": list(getattr(rule, "exclude_group_keys", []) or []),
            }
        )

        if getattr(rule, "exclude_rule_codes", None):
            suppressed_rule_codes.update(rule.exclude_rule_codes)
        if getattr(rule, "exclude_group_keys", None):
            suppressed_group_keys.update(rule.exclude_group_keys)

        if total_score >= thresholds.decline:
            break

    rule_score = min(round(total_score, 2), 100.0)
    risk_score = rule_score
    ml_result: dict[str, Any] | None = None
    degradation_reasons: list[str] = []

    if ml_enabled:
        try:
            ml_result = ml_fraud_service.predict(transaction_data)
            risk_score = min(
                ml_fraud_service.combine_scores(
                    rule_score,
                    float(ml_result["risk_score"]),
                    rule_weight=ml_result.get("blend_weights", {}).get("rule_weight"),
                    ml_weight=ml_result.get("blend_weights", {}).get("ml_weight"),
                ),
                100.0,
            )
            score_breakdown.append(
                {
                    "source": "ml",
                    "model_version": ml_result.get("model_version"),
                    "risk_score": float(ml_result["risk_score"]),
                    "fraud_probability": float(ml_result["fraud_probability"]),
                    "confidence": float(ml_result["confidence"]),
                    "blend_weights": ml_result.get("blend_weights", {}),
                }
            )
        except Exception:
            logger.exception(
                "ml_scoring_failed",
                extra={"organisation_id": scoring_context.get("organisation_id")},
            )
            degradation_reasons.append("ml_scoring_failed")
            ml_result = {
                "model_version": "unavailable",
                "risk_score": 0.0,
                "fraud_probability": 0.0,
                "confidence": 0.0,
                "feature_contributions": [],
                "feature_diagnostics": {},
                "blend_weights": {},
            }

    if risk_score >= thresholds.decline:
        decision = FraudDecision.decline
    elif risk_score >= thresholds.review:
        decision = FraudDecision.review
    else:
        decision = FraudDecision.approve

    if not reason_codes:
        reason_codes.append(ReasonCode.low_signal_profile)

    explanation = {
        "summary": {
            "rule_score": rule_score,
            "risk_score": risk_score,
            "decision": decision.value,
            "matched_rule_count": len(matched_rules),
            "suppressed_rule_codes": sorted(suppressed_rule_codes),
            "suppressed_group_keys": sorted(suppressed_group_keys),
            "suppression_counts": dict(suppression_counts),
        },
        "threshold_profile": scoring_context.get("threshold_profile", {}),
        "rule_evaluations": score_breakdown,
        "reason_code_totals": reason_code_totals,
        "feature_diagnostics": (ml_result or {}).get("feature_diagnostics", {}),
    }

    return {
        "risk_score": risk_score,
        "rule_score": rule_score,
        "ml_result": ml_result,
        "decision": decision,
        "reason_codes": reason_codes,
        "matched_rules": matched_rules,
        "reason_code_totals": reason_code_totals,
        "score_breakdown": score_breakdown,
        "thresholds": scoring_context["thresholds"],
        "threshold_profile": scoring_context.get("threshold_profile", {}),
        "scoring_context": scoring_context,
        "rules_version": scoring_context["rules_version"],
        "rules_hash": scoring_context["rules_hash"],
        "scoring_version": scoring_context["scoring_version"],
        "ml_enabled": ml_enabled,
        "degradation_reasons": degradation_reasons,
        "evaluated_data": transaction_data,
        "explanation": explanation,
    }


def score_transaction(db: Session, payload: TransactionCreate) -> dict[str, Any]:
    enrichment_data, degradation_reasons = _safe_enrichment_lookup(db, payload)

    transaction_data = transaction_service.normalize_transaction_data_with_enrichment(
        payload, enrichment_data
    )
    try:
        velocity_signals = velocity_service.get_velocity_signals(db, payload)
    except Exception:
        logger.exception(
            "velocity_lookup_failed",
            extra={"organisation_id": payload.organisation_id},
        )
        degradation_reasons.append("velocity_lookup_failed")
        velocity_signals = {}
    transaction_data.update(velocity_signals)
    try:
        device_signals = device_fingerprint_service.get_device_signals(db, payload)
    except Exception:
        logger.exception(
            "device_signal_lookup_failed",
            extra={"organisation_id": payload.organisation_id},
        )
        degradation_reasons.append("device_signal_lookup_failed")
        device_signals = {}
    transaction_data.update(device_signals)

    effective_rules = fraud_rule_service.list_effective_fraud_rules_service(
        db,
        organisation_id=payload.organisation_id,
    )
    thresholds, threshold_profile = _load_thresholds(
        db,
        payload.organisation_id,
        channel=getattr(payload, "channel", None),
        transaction_type=getattr(payload, "transaction_type", None),
    )
    scoring_context = _build_scoring_context(
        organisation_id=payload.organisation_id,
        transaction_data=transaction_data,
        effective_rules=effective_rules,
        thresholds=thresholds,
        threshold_profile=threshold_profile,
    )
    return _score_with_rules(
        transaction_data=transaction_data,
        effective_rules=effective_rules,
        thresholds=thresholds,
        scoring_context=scoring_context,
        ml_enabled=ml_fraud_service.is_ml_scoring_enabled(),
    ) | {"degradation_reasons": degradation_reasons}


def replay_scoring_snapshot(scoring_snapshot: dict[str, Any]) -> dict[str, Any]:
    scoring_context = dict(scoring_snapshot.get("scoring_context") or {})
    rules_payload = scoring_snapshot.get("rules") or scoring_context.get("rules") or []
    effective_rules = [_deserialize_rule_snapshot(rule) for rule in rules_payload]
    thresholds_payload = scoring_snapshot.get("thresholds") or scoring_context.get("thresholds") or {}
    thresholds = ScoreThresholds(
        review=_coerce_threshold_value(
            thresholds_payload.get("review", DEFAULT_REVIEW_THRESHOLD),
            DEFAULT_REVIEW_THRESHOLD,
        ),
        decline=_coerce_threshold_value(
            thresholds_payload.get("decline", DEFAULT_DECLINE_THRESHOLD),
            DEFAULT_DECLINE_THRESHOLD,
        ),
        source=str(thresholds_payload.get("source", "snapshot")),
    )
    threshold_profile = dict(scoring_snapshot.get("threshold_profile") or scoring_context.get("threshold_profile") or {})
    transaction_data = dict(scoring_snapshot.get("evaluated_data") or {})
    if not transaction_data:
        raise NotFoundError("Scoring snapshot does not contain replayable transaction data")

    replay_context = {
        **scoring_context,
        "organisation_id": scoring_snapshot.get("organisation_id", scoring_context.get("organisation_id")),
        "rules_version": scoring_snapshot.get("rules_version", scoring_context.get("rules_version")),
        "rules_hash": scoring_snapshot.get("rules_hash", scoring_context.get("rules_hash")),
        "scoring_version": scoring_snapshot.get("scoring_version", scoring_context.get("scoring_version", SCORING_VERSION)),
        "thresholds": {
            "review": thresholds.review,
            "decline": thresholds.decline,
            "source": thresholds.source,
        },
        "threshold_profile": threshold_profile,
        "rules": rules_payload,
        "rules_count": len(rules_payload),
        "feature_columns": scoring_context.get("feature_columns", list(ml_fraud_service.FEATURE_COLUMNS)),
        "evaluated_keys": sorted(transaction_data.keys()),
    }
    replay_result = _score_with_rules(
        transaction_data=transaction_data,
        effective_rules=effective_rules,
        thresholds=thresholds,
        scoring_context=replay_context,
        ml_enabled=False,
    )

    original_ml = scoring_snapshot.get("ml_result")
    if isinstance(original_ml, dict) and original_ml:
        replay_result["ml_result"] = original_ml
        replay_result["score_breakdown"].append(
            {
                "source": "ml",
                "model_version": original_ml.get("model_version"),
                "risk_score": float(original_ml.get("risk_score", 0.0)),
                "fraud_probability": float(original_ml.get("fraud_probability", 0.0)),
                "confidence": float(original_ml.get("confidence", 0.0)),
                "blend_weights": original_ml.get("blend_weights", {}),
                "replayed_from_snapshot": True,
            }
        )
        replay_result["risk_score"] = min(
            ml_fraud_service.combine_scores(
                replay_result["rule_score"],
                float(original_ml.get("risk_score", 0.0)),
                rule_weight=original_ml.get("blend_weights", {}).get("rule_weight"),
                ml_weight=original_ml.get("blend_weights", {}).get("ml_weight"),
            ),
            100.0,
        )
        replay_result["decision"] = (
            FraudDecision.decline
            if replay_result["risk_score"] >= thresholds.decline
            else FraudDecision.review
            if replay_result["risk_score"] >= thresholds.review
            else FraudDecision.approve
        )
        replay_result["explanation"]["summary"]["risk_score"] = replay_result["risk_score"]
        replay_result["explanation"]["summary"]["decision"] = replay_result["decision"].value
        replay_result["explanation"]["summary"]["replayed_from_snapshot"] = True

    original_summary = scoring_snapshot.get("decision_summary") or {}
    replay_result["replay"] = {
        "matches_original_decision": original_summary.get("risk_score") == replay_result["risk_score"]
        and original_summary.get("rule_score") == replay_result["rule_score"]
        and original_summary.get("decision") == replay_result["decision"].value,
        "original_decision": original_summary.get("decision"),
        "original_risk_score": original_summary.get("risk_score"),
        "original_rule_score": original_summary.get("rule_score"),
        "original_model_version": original_summary.get("model_version"),
    }
    return replay_result
