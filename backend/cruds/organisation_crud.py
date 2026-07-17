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


def list_organisations(db: Session, *, skip: int = 0, limit: int = 100) -> list[Organisation]:
    return db.query(Organisation).offset(skip).limit(limit).all()


def update_organisation(db: Session, organisation: Organisation, **updates) -> Organisation:
    for field, value in updates.items():
        if value is not None:
            setattr(organisation, field, value)
    db.commit()
    db.refresh(organisation)
    return organisation


def delete_organisation(db: Session, organisation: Organisation) -> None:
    db.delete(organisation)
    db.commit()
