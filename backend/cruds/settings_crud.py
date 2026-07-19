from sqlalchemy.orm import Session

from models.settings_models import OrganisationSettings


def create_settings(db: Session, **data) -> OrganisationSettings:
    settings = OrganisationSettings(**data)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def get_settings_by_organisation_id(
    db: Session, organisation_id: int
) -> OrganisationSettings | None:
    return (
        db.query(OrganisationSettings)
        .filter(OrganisationSettings.organisation_id == organisation_id)
        .first()
    )


def update_settings(
    db: Session, settings: OrganisationSettings, **updates
) -> OrganisationSettings:
    for field, value in updates.items():
        if value is not None:
            setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
