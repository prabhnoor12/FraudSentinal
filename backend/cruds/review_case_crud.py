from datetime import datetime

from sqlalchemy.orm import Session

from models.review_case_models import ReviewCase


def create_review_case(db: Session, *, commit: bool = True, **data) -> ReviewCase:
    payload = dict(data)
    payload["case_metadata"] = payload.pop("metadata", {})
    review_case = ReviewCase(**payload)
    db.add(review_case)
    if commit:
        db.commit()
        db.refresh(review_case)
    return review_case


def get_review_case_by_id(db: Session, case_id: int) -> ReviewCase | None:
    return db.query(ReviewCase).filter(ReviewCase.id == case_id).first()


def get_review_case_by_decision_id(db: Session, decision_id: int) -> ReviewCase | None:
    return db.query(ReviewCase).filter(ReviewCase.decision_id == decision_id).first()


def list_review_cases(
    db: Session,
    *,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    decision_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[ReviewCase]:
    query = db.query(ReviewCase)
    if organisation_id is not None:
        query = query.filter(ReviewCase.organisation_id == organisation_id)
    if transaction_id is not None:
        query = query.filter(ReviewCase.transaction_id == transaction_id)
    if decision_id is not None:
        query = query.filter(ReviewCase.decision_id == decision_id)
    if status is not None:
        query = query.filter(ReviewCase.status == status)
    return query.order_by(ReviewCase.created_at.desc()).limit(limit).all()


def update_review_case(db: Session, review_case: ReviewCase, *, commit: bool = True, **updates) -> ReviewCase:
    payload = dict(updates)
    if "metadata" in payload:
        payload["case_metadata"] = payload.pop("metadata")
    for field, value in payload.items():
        setattr(review_case, field, value)
    if commit:
        db.commit()
        db.refresh(review_case)
    return review_case


def mark_review_case_resolved(db: Session, review_case: ReviewCase, *, resolution: str | None = None) -> ReviewCase:
    review_case.status = "resolved"
    review_case.resolution = resolution
    review_case.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(review_case)
    return review_case
