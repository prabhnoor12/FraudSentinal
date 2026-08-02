from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from cruds import transaction_crud
from schemas.transaction_schemas import TransactionCreate


def _count_with_current(historical_count: int) -> int:
    return historical_count + 1


def _sum_with_current(historical_amount: float, current_amount: float) -> float:
    return round(historical_amount + float(current_amount), 2)


def get_velocity_signals(db: Session, payload: TransactionCreate) -> dict[str, float | int]:
    """Compute org-scoped transaction history signals for a customer."""
    if not payload.customer_id:
        return {}

    now = datetime.now(UTC)
    windows = {
        "1hour": now - timedelta(hours=1),
        "24hour": now - timedelta(hours=24),
    }
    signals: dict[str, float | int] = {}

    for label, since in windows.items():
        tx_count = transaction_crud.count_transactions_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
        )
        amount_velocity = transaction_crud.sum_transaction_amount_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
        )
        unique_ips = transaction_crud.count_unique_ip_addresses_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
        )
        unique_devices = transaction_crud.count_unique_values_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="device_id",
        )
        unique_payment_methods = transaction_crud.count_unique_values_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="payment_method",
        )
        unique_billing_countries = transaction_crud.count_unique_values_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="billing_country",
        )
        unique_shipping_countries = transaction_crud.count_unique_values_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="shipping_country",
        )
        ip_seen = bool(payload.ip_address) and transaction_crud.has_ip_address_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            ip_address=payload.ip_address,
            since=since,
        )
        device_seen = bool(payload.device_id) and transaction_crud.has_value_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="device_id",
            value=payload.device_id,
        )
        payment_method_seen = transaction_crud.has_value_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="payment_method",
            value=payload.payment_method,
        )
        billing_country_seen = bool(payload.billing_country) and transaction_crud.has_value_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="billing_country",
            value=payload.billing_country,
        )
        shipping_country_seen = bool(payload.shipping_country) and transaction_crud.has_value_since(
            db,
            organisation_id=payload.organisation_id,
            customer_id=payload.customer_id,
            since=since,
            column_name="shipping_country",
            value=payload.shipping_country,
        )

        signals[f"tx_count_{label}"] = _count_with_current(tx_count)
        signals[f"amount_velocity_{label}"] = _sum_with_current(
            amount_velocity,
            payload.amount,
        )
        signals[f"unique_ips_{label}"] = unique_ips + (
            0 if not payload.ip_address or ip_seen else 1
        )
        signals[f"unique_devices_{label}"] = unique_devices + (
            0 if device_seen or not payload.device_id else 1
        )
        signals[f"unique_payment_methods_{label}"] = unique_payment_methods + (
            0 if payment_method_seen else 1
        )
        signals[f"unique_billing_countries_{label}"] = unique_billing_countries + (
            0 if billing_country_seen or not payload.billing_country else 1
        )
        signals[f"unique_shipping_countries_{label}"] = unique_shipping_countries + (
            0 if shipping_country_seen or not payload.shipping_country else 1
        )

    # Preserve compatibility with existing velocity rules while switching to
    # persisted history when a customer identifier is available.
    signals["transactions_last_24h"] = max(
        int(payload.transactions_last_24h),
        int(signals["tx_count_24hour"]),
    )
    signals["known_devices_count"] = int(unique_devices)

    return signals
