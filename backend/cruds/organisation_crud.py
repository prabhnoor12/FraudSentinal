from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.organisation_models import Organisation


def create_organisation(
    db: Session,
    *,
    name: str,
    slug: str | None = None,
    is_active: bool = True,
) -> Organisation:
    organisation = Organisation(name=name, slug=slug, is_active=is_active)
    db.add(organisation)
    db.commit()
    db.refresh(organisation)
    return organisation


def get_organisation_by_id(db: Session, organisation_id: int) -> Organisation | None:
    return db.query(Organisation).filter(Organisation.id == organisation_id).first()


def get_organisation_by_slug(db: Session, slug: str) -> Organisation | None:
    return db.query(Organisation).filter(Organisation.slug == slug).first()


def get_organisation_by_billing_subscription_external_id(
    db: Session, subscription_external_id: str
) -> Organisation | None:
    return (
        db.query(Organisation)
        .filter(Organisation.billing_subscription_external_id == subscription_external_id)
        .first()
    )


def get_organisation_by_billing_customer_external_id(
    db: Session, customer_external_id: str
) -> Organisation | None:
    return (
        db.query(Organisation)
        .filter(Organisation.billing_customer_external_id == customer_external_id)
        .first()
    )


def list_organisations(
    db: Session,
    *,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[Organisation]:
    query = db.query(Organisation)
    if organisation_id is not None:
        query = query.filter(Organisation.id == organisation_id)
    order_column = {
        "created_at": Organisation.created_at,
        "updated_at": Organisation.updated_at,
        "name": Organisation.name,
        "id": Organisation.id,
    }.get(sort_by, Organisation.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(Organisation.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_organisations(db: Session, *, organisation_id: int | None = None) -> int:
    query = db.query(func.count(Organisation.id))
    if organisation_id is not None:
        query = query.filter(Organisation.id == organisation_id)
    return query.scalar() or 0


def update_organisation(
    db: Session, organisation: Organisation, *, commit: bool = True, **updates
) -> Organisation:
    for field, value in updates.items():
        if value is not None:
            setattr(organisation, field, value)
    if commit:
        db.commit()
        db.refresh(organisation)
    else:
        db.flush()
    return organisation


def delete_organisation(db: Session, organisation: Organisation) -> None:
    db.delete(organisation)
    db.commit()
