from __future__ import annotations

from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.transaction_schemas import TransactionCreate


RISKY_PAYMENT_METHODS = {"crypto", "gift_card", "prepaid_card", "wire_transfer"}
MANUAL_REVIEW_CHANNELS = {"manual", "call_center", "moto"}


def score_transaction(payload: TransactionCreate) -> dict:
    score = 0.0
    reason_codes: list[ReasonCode] = []

    def add_signal(points: float, reason_code: ReasonCode) -> None:
        nonlocal score
        score += points
        if reason_code not in reason_codes:
            reason_codes.append(reason_code)

    if payload.amount >= 2000:
        add_signal(35, ReasonCode.high_amount)
    elif payload.amount >= 1000:
        add_signal(20, ReasonCode.high_amount)
    elif payload.amount >= 500:
        add_signal(10, ReasonCode.high_amount)

    if payload.transactions_last_24h >= 10:
        add_signal(25, ReasonCode.velocity_spike)
    elif payload.transactions_last_24h >= 5:
        add_signal(15, ReasonCode.velocity_spike)
    elif payload.transactions_last_24h >= 3:
        add_signal(8, ReasonCode.velocity_spike)

    if payload.failed_attempts_last_24h >= 5:
        add_signal(25, ReasonCode.repeated_failed_attempts)
    elif payload.failed_attempts_last_24h >= 2:
        add_signal(15, ReasonCode.repeated_failed_attempts)
    elif payload.failed_attempts_last_24h >= 1:
        add_signal(8, ReasonCode.repeated_failed_attempts)

    if payload.account_age_days is not None:
        if payload.account_age_days < 3:
            add_signal(25, ReasonCode.new_account)
        elif payload.account_age_days < 14:
            add_signal(15, ReasonCode.new_account)
        elif payload.account_age_days < 30:
            add_signal(8, ReasonCode.new_account)

    if (
        payload.billing_country
        and payload.shipping_country
        and payload.billing_country.strip().upper() != payload.shipping_country.strip().upper()
    ):
        add_signal(15, ReasonCode.cross_border_mismatch)

    if not payload.device_id:
        add_signal(10, ReasonCode.missing_device)

    if payload.payment_method.strip().lower() in RISKY_PAYMENT_METHODS:
        add_signal(20, ReasonCode.risky_payment_method)

    if payload.channel.strip().lower() in MANUAL_REVIEW_CHANNELS:
        add_signal(10, ReasonCode.manual_entry)

    risk_score = min(round(score, 2), 100.0)
    if risk_score >= 70:
        decision = FraudDecision.decline
    elif risk_score >= 40:
        decision = FraudDecision.review
    else:
        decision = FraudDecision.approve

    if not reason_codes:
        reason_codes.append(ReasonCode.low_signal_profile)

    return {
        "risk_score": risk_score,
        "decision": decision,
        "reason_codes": reason_codes,
    }
