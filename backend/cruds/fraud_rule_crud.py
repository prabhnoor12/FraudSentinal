from sqlalchemy.orm import Session

from models.fraud_rule_models import FraudRule


def create_fraud_rule(db: Session, **data) -> FraudRule:
    fraud_rule = FraudRule(**data)
    db.add(fraud_rule)
    db.commit()
    db.refresh(fraud_rule)
    return fraud_rule


def get_fraud_rule_by_id(db: Session, rule_id: int) -> FraudRule | None:
    return db.query(FraudRule).filter(FraudRule.id == rule_id).first()


def get_fraud_rule_by_code(
    db: Session,
    *,
    rule_code: str,
    organisation_id: int | None = None,
) -> FraudRule | None:
    query = db.query(FraudRule).filter(FraudRule.rule_code == rule_code)
    if organisation_id is None:
        query = query.filter(FraudRule.organisation_id.is_(None))
    else:
        query = query.filter(FraudRule.organisation_id == organisation_id)
    return query.first()


def list_fraud_rules(
    db: Session,
    *,
    organisation_id: int | None = None,
    enabled: bool | None = None,
    limit: int = 100,
) -> list[FraudRule]:
    query = db.query(FraudRule)
    if organisation_id is not None:
        query = query.filter(FraudRule.organisation_id == organisation_id)
    if enabled is not None:
        query = query.filter(FraudRule.enabled == enabled)
    return (
        query.order_by(FraudRule.priority.asc(), FraudRule.id.asc()).limit(limit).all()
    )


def list_effective_fraud_rules(
    db: Session,
    *,
    organisation_id: int | None = None,
) -> list[FraudRule]:
    query = db.query(FraudRule).filter(FraudRule.enabled == True)  # noqa: E712
    if organisation_id is None:
        return (
            query.filter(FraudRule.organisation_id.is_(None))
            .order_by(FraudRule.priority.asc(), FraudRule.id.asc())
            .all()
        )

    rules = (
        query.filter(
            (FraudRule.organisation_id.is_(None))
            | (FraudRule.organisation_id == organisation_id)
        )
        .order_by(FraudRule.priority.asc(), FraudRule.id.asc())
        .all()
    )

    effective_rules_by_code: dict[str, FraudRule] = {}
    for rule in rules:
        existing = effective_rules_by_code.get(rule.rule_code)
        if existing is None:
            effective_rules_by_code[rule.rule_code] = rule
            continue
        if existing.organisation_id is None and rule.organisation_id == organisation_id:
            effective_rules_by_code[rule.rule_code] = rule
    return list(effective_rules_by_code.values())


def update_fraud_rule(db: Session, fraud_rule: FraudRule, **updates) -> FraudRule:
    for field, value in updates.items():
        setattr(fraud_rule, field, value)
    db.commit()
    db.refresh(fraud_rule)
    return fraud_rule
