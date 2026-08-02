from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Any

from sqlalchemy.orm import Session

from schemas.decision_schemas import DecisionCreate
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from schemas.risk_signal_schemas import RiskSignalCreate
from services import (
    decision_service,
    device_fingerprint_service,
    entitlement_service,
    fraud_rule_service,
    review_case_service,
    risk_signal_service,
    scoring_service,
    transaction_service,
)


def _build_scoring_snapshot(
    scoring_source: dict[str, Any] | Session,
    organisation_id: int | None = None,
) -> dict[str, Any]:
    """Capture the exact rule configuration used for the decision.

    The main path passes a scoring context dict. Tests still pass a session and
    org id, so we keep that path for compatibility.
    """
    if isinstance(scoring_source, dict):
        scoring_context = scoring_source.get("scoring_context") or scoring_source
        rules_version = scoring_context.get("rules_version") or scoring_source.get("rules_version")
        rules_hash = scoring_context.get("rules_hash") or scoring_source.get("rules_hash")
        scoring_version = scoring_context.get("scoring_version") or scoring_source.get("scoring_version")
        rules_count = scoring_context.get("rules_count") or scoring_source.get("rules_count")
        thresholds = scoring_context.get("thresholds") or scoring_source.get("thresholds")
        threshold_profile = scoring_context.get("threshold_profile") or scoring_source.get("threshold_profile") or {}
        feature_columns = scoring_context.get("feature_columns") or scoring_source.get("feature_columns") or []
        evaluated_keys = scoring_context.get("evaluated_keys") or scoring_source.get("evaluated_keys") or []
        rules = scoring_context.get("rules") or scoring_source.get("rules") or []
        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "organisation_id": scoring_context.get("organisation_id"),
            "rules_version": rules_version,
            "rules_hash": rules_hash,
            "scoring_version": scoring_version,
            "rules_count": rules_count,
            "thresholds": thresholds,
            "threshold_profile": threshold_profile,
            "feature_columns": feature_columns,
            "evaluated_keys": evaluated_keys,
            "evaluated_data": scoring_source.get("evaluated_data", {}),
            "rules": rules,
            "scoring_context": scoring_context,
            "score_breakdown": scoring_source.get("score_breakdown", []),
            "explanation": scoring_source.get("explanation", {}),
            "ml_result": scoring_source.get("ml_result"),
            "decision_summary": {
                "risk_score": scoring_source.get("risk_score"),
                "rule_score": scoring_source.get("rule_score"),
                "decision": getattr(scoring_source.get("decision"), "value", scoring_source.get("decision")),
                "model_version": (scoring_source.get("ml_result") or {}).get(
                    "model_version"
                ),
                "degradation_reasons": scoring_source.get("degradation_reasons", []),
            },
            "replay_ready": True,
        }

    db = scoring_source
    effective_rules = fraud_rule_service.list_effective_fraud_rules_service(
        db, organisation_id=organisation_id
    )
    fallback_context = scoring_service._build_scoring_context(
        organisation_id=organisation_id,
        transaction_data={},
        effective_rules=effective_rules,
        thresholds=scoring_service.ScoreThresholds(
            review=scoring_service.DEFAULT_REVIEW_THRESHOLD,
            decline=scoring_service.DEFAULT_DECLINE_THRESHOLD,
            source="defaults",
        ),
        threshold_profile={
            "profile_key": f"tenant:{organisation_id or 'global'}|default",
            "profile_source": "defaults",
            "profile_overrides": {},
        },
    )
    fallback_context["captured_at"] = datetime.now(UTC).isoformat()
    return fallback_context


def check_fraud_service(db: Session, payload: FraudCheckRequest) -> FraudCheckResponse:
    started_at = time.perf_counter()
    score_result = scoring_service.score_transaction(db, payload)
    transaction_data = score_result.get("evaluated_data") or transaction_service.normalize_transaction_data(payload)
    scoring_context = score_result.get("scoring_context") or {}
    rule_score = score_result.get("rule_score", score_result.get("risk_score", 0.0))
    rules_version = score_result.get("rules_version") or scoring_context.get("rules_version") or "ruleset-unknown"
    rules_hash = score_result.get("rules_hash") or scoring_context.get("rules_hash") or "unknown"
    thresholds = score_result.get("thresholds") or scoring_context.get("thresholds") or {}

    try:
        transaction = transaction_service.create_transaction_record(
            db, payload, commit=False
        )
        db.flush()

        scoring_snapshot = _build_scoring_snapshot(score_result)

        decision = decision_service.create_decision_record(
            db,
            DecisionCreate(
                transaction_id=transaction.id,
                user_id=transaction.user_id,
                organisation_id=transaction.organisation_id,
                risk_score=score_result["risk_score"],
                decision=score_result["decision"],
                reason_codes=score_result["reason_codes"],
                scoring_snapshot=scoring_snapshot,
            ),
            commit=False,
        )
        db.flush()

        for rule in score_result.get("matched_rules", []):
            risk_signal_service.create_risk_signal_service(
                db,
                RiskSignalCreate(
                    transaction_id=transaction.id,
                    decision_id=decision.id,
                    organisation_id=transaction.organisation_id,
                    user_id=transaction.user_id,
                    rule_id=rule.id,
                    rule_code=rule.rule_code,
                    reason_code=rule.reason_code,
                    weight=rule.weight,
                    details={
                        "field_name": rule.field_name,
                        "operator": rule.operator,
                        "comparison_value": rule.comparison_value,
                        "secondary_field_name": rule.secondary_field_name,
                        "matched_value": transaction_data.get(rule.field_name),
                        "secondary_value": transaction_data.get(
                            rule.secondary_field_name
                        )
                        if rule.secondary_field_name
                        else None,
                    },
                ),
                commit=False,
            )

        review_case_service.create_review_case_if_needed(
            db,
            transaction_id=transaction.id,
            decision_id=decision.id,
            organisation_id=transaction.organisation_id,
            user_id=transaction.user_id,
            decision_value=decision.decision,
            commit=False,
        )
        device_fingerprint_service.remember_device_fingerprint(
            db,
            payload,
            commit=False,
        )
        entitlement_service.record_consumption(
            db,
            organisation_id=transaction.organisation_id,
            user_id=transaction.user_id,
            meter_key="fraud_checks",
            units=1.0,
            currency=transaction.currency,
            description=f"Fraud check for transaction {transaction.id}",
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transaction)
    db.refresh(decision)

    ml_result = score_result.get("ml_result") or {}
    processing_time_ms = round((time.perf_counter() - started_at) * 1000, 2)

    return FraudCheckResponse(
        transaction_id=transaction.id,
        decision_id=decision.id,
        risk_score=decision.risk_score,
        rule_score=rule_score,
        ml_score=ml_result.get("risk_score"),
        decision=decision.decision,
        reason_codes=decision.reason_codes or [],
        matched_rule_codes=[rule.rule_code for rule in score_result.get("matched_rules", [])],
        rules_version=rules_version,
        rules_hash=rules_hash,
        model_version=ml_result.get("model_version"),
        thresholds=thresholds,
        processing_time_ms=processing_time_ms,
        degradation_reasons=score_result.get("degradation_reasons", []),
        score_breakdown=score_result.get("score_breakdown", []),
        scoring_snapshot=scoring_snapshot,
        checked_at=decision.created_at,
    )
