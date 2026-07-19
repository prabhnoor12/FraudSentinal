from __future__ import annotations

from sqlalchemy.orm import Session

from cruds import organisation_crud, transaction_crud, user_crud
from schemas.transaction_schemas import TransactionCreate, TransactionOut
from utils.exception_handling_utils import NotFoundError


def _ensure_transaction_owners_exist(
    db: Session, *, user_id: int, organisation_id: int
) -> None:
    if not user_crud.get_user_by_id(db, user_id):
        raise NotFoundError("User not found")
    if not organisation_crud.get_organisation_by_id(db, organisation_id):
        raise NotFoundError("Organisation not found")


def normalize_transaction_data(payload: TransactionCreate) -> dict:
    data = payload.model_dump()
    data["currency"] = data["currency"].strip().upper()
    data["payment_method"] = data["payment_method"].strip().lower()
    data["channel"] = data["channel"].strip().lower()

    if data.get("customer_email"):
        data["customer_email"] = data["customer_email"].strip().lower()
    if data.get("billing_country"):
        data["billing_country"] = data["billing_country"].strip().upper()
    if data.get("shipping_country"):
        data["shipping_country"] = data["shipping_country"].strip().upper()
    if data.get("ip_address"):
        data["ip_address"] = data["ip_address"].strip()

    return data


def normalize_transaction_data_with_enrichment(
    payload: TransactionCreate,
    enrichment_data: dict,
) -> dict:
    """Normalize transaction data and merge with enrichment signals.

    Args:
        payload: The transaction create payload
        enrichment_data: Flat dictionary from enrichment_service.get_enriched_transaction_data()

    Returns:
        Merged dictionary with all transaction and enrichment fields
    """
    # Start with basic normalization
    data = normalize_transaction_data(payload)

    # Merge enrichment data (enrichment takes precedence for overlapping fields)
    data.update(enrichment_data)

    return data


def serialize_transaction(transaction) -> TransactionOut:
    return TransactionOut(
        id=transaction.id,
        user_id=transaction.user_id,
        organisation_id=transaction.organisation_id,
        external_transaction_id=transaction.external_transaction_id,
        amount=transaction.amount,
        currency=transaction.currency,
        payment_method=transaction.payment_method,
        channel=transaction.channel,
        customer_id=transaction.customer_id,
        customer_email=transaction.customer_email,
        billing_country=transaction.billing_country,
        shipping_country=transaction.shipping_country,
        ip_address=transaction.ip_address,
        device_id=transaction.device_id,
        account_age_days=transaction.account_age_days,
        transactions_last_24h=transaction.transactions_last_24h,
        failed_attempts_last_24h=transaction.failed_attempts_last_24h,
        metadata=transaction.transaction_metadata or {},
        created_at=transaction.created_at,
    )


def create_transaction_record(
    db: Session,
    payload: TransactionCreate,
    *,
    commit: bool = True,
):
    _ensure_transaction_owners_exist(
        db, user_id=payload.user_id, organisation_id=payload.organisation_id
    )
    return transaction_crud.create_transaction(
        db, commit=commit, **normalize_transaction_data(payload)
    )


def create_transaction_service(
    db: Session,
    payload: TransactionCreate,
    *,
    audit_ctx=None,
) -> TransactionOut:
    transaction = create_transaction_record(db, payload, commit=True)
    return serialize_transaction(transaction)


def get_transaction_service(
    db: Session, transaction_id: int, organisation_id: int | None = None
) -> TransactionOut:
    transaction = transaction_crud.get_transaction_by_id(db, transaction_id)
    if not transaction:
        raise NotFoundError("Transaction not found")

    if organisation_id is not None and transaction.organisation_id != organisation_id:
        raise NotFoundError("Transaction not found")

    return serialize_transaction(transaction)


def list_transactions_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    limit: int = 100,
) -> list[TransactionOut]:
    transactions = transaction_crud.list_transactions(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        limit=limit,
    )
    return [serialize_transaction(transaction) for transaction in transactions]
