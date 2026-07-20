from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import asyncio
import json
import time
from threading import RLock

from sqlalchemy.orm import Session

from cruds import billing_crud, limit_tracking_crud, organisation_crud, usage_crud, user_crud
from redis import RedisClient, get_redis_url
from utils.exception_handling_utils import (
    FeatureNotAvailableError,
    NotFoundError,
    QuotaExceededError,
    SubscriptionInactiveError,
)

ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}
PLAN_ALIASES = {"pro": "growth", "premium": "growth"}


@dataclass(frozen=True)
class PlanDefinition:
    code: str
    features: frozenset[str]
    quotas: dict[str, float | None]
    unit_prices: dict[str, float]


@dataclass(frozen=True)
class EntitlementSnapshot:
    organisation_id: int
    plan_code: str
    subscription_status: str
    trial_ends_at: datetime | None
    features: frozenset[str]
    quotas: dict[str, float | None]

    @property
    def subscription_active(self) -> bool:
        return _is_subscription_active(self.subscription_status, self.trial_ends_at)


@dataclass(frozen=True)
class ResolvedQuota:
    quota_key: str
    limit_value: float | None
    period: str | None
    current_usage: float
    remaining: float | None
    usage_limit_id: int | None


PLAN_DEFINITIONS: dict[str, PlanDefinition] = {
    "starter": PlanDefinition(
        code="starter",
        features=frozenset(
            {
                "billing",
                "fraud_detection",
                "limit_tracking",
                "usage",
            }
        ),
        quotas={
            "fraud_checks": 1_000.0,
        },
        unit_prices={
            "fraud_checks": 0.05,
        },
    ),
    "growth": PlanDefinition(
        code="growth",
        features=frozenset(
            {
                "billing",
                "enrichment",
                "fraud_detection",
                "limit_tracking",
                "usage",
            }
        ),
        quotas={
            "enrichment_lookups": 5_000.0,
            "fraud_checks": 10_000.0,
        },
        unit_prices={
            "enrichment_lookups": 0.01,
            "fraud_checks": 0.03,
        },
    ),
    "enterprise": PlanDefinition(
        code="enterprise",
        features=frozenset(
            {
                "billing",
                "enrichment",
                "fraud_detection",
                "limit_tracking",
                "usage",
            }
        ),
        quotas={
            "enrichment_lookups": None,
            "fraud_checks": None,
        },
        unit_prices={
            "enrichment_lookups": 0.0,
            "fraud_checks": 0.02,
        },
    ),
}

ALL_FEATURES = frozenset(
    feature for plan in PLAN_DEFINITIONS.values() for feature in plan.features
)
METERED_RESOURCES = ("fraud_checks", "enrichment_lookups")
ENTITLEMENT_CACHE_TTL_SECONDS = 30


class EntitlementResponseCache:
    def __init__(self) -> None:
        self._memory_cache: dict[str, tuple[float, dict[str, object]]] = {}
        self._lock = RLock()
        self._redis_client: RedisClient | None = None
        self._redis_url: str | None = None

    def get(self, key: str) -> dict[str, object] | None:
        now = time.monotonic()
        with self._lock:
            cached = self._memory_cache.get(key)
            if cached and cached[0] > now:
                return dict(cached[1])
            if cached:
                self._memory_cache.pop(key, None)

        redis_client = self._get_redis_client()
        if redis_client is None:
            return None

        try:
            payload = self._run_redis_call(redis_client.get(key))
        except Exception:
            return None
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        expires_at = time.monotonic() + ttl_seconds
        payload = dict(value)
        with self._lock:
            self._memory_cache[key] = (expires_at, payload)

        redis_client = self._get_redis_client()
        if redis_client is None:
            return

        try:
            self._run_redis_call(
                redis_client.set(
                    key,
                    json.dumps(payload, default=str, sort_keys=True),
                    ex=ttl_seconds,
                )
            )
        except Exception:
            return

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._memory_cache.pop(key, None)

    def _get_redis_client(self) -> RedisClient | None:
        redis_url = get_redis_url()
        if not redis_url:
            return None
        with self._lock:
            if self._redis_client and self._redis_url == redis_url:
                return self._redis_client
            self._redis_url = redis_url
            self._redis_client = RedisClient(redis_url)
            return self._redis_client

    @staticmethod
    def _run_redis_call(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("Blocking entitlement cache helper cannot run inside an active loop")


entitlement_cache = EntitlementResponseCache()


def _normalize_plan_code(plan_code: str | None) -> str:
    normalized = (plan_code or "starter").strip().lower()
    normalized = PLAN_ALIASES.get(normalized, normalized)
    return normalized if normalized in PLAN_DEFINITIONS else "starter"


def _is_subscription_active(
    subscription_status: str | None,
    trial_ends_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    normalized_status = (subscription_status or "").strip().lower()
    if normalized_status not in ACTIVE_SUBSCRIPTION_STATUSES:
        return False
    if normalized_status == "trialing" and trial_ends_at is not None:
        current_time = now or datetime.now(UTC)
        trial_deadline = _as_utc(trial_ends_at)
        return trial_deadline >= current_time
    return True


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_bool_string(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _period_bounds(period: str, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    current_time = _as_utc(now or datetime.now(UTC))
    normalized = (period or "monthly").strip().lower()

    if normalized == "daily":
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    if normalized == "weekly":
        start = (
            current_time - timedelta(days=current_time.weekday())
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=7)

    start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _monthly_bounds(*, now: datetime | None = None) -> tuple[datetime, datetime]:
    current_time = _as_utc(now or datetime.now(UTC))
    start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = monthrange(start.year, start.month)[1]
    end = start + timedelta(days=days_in_month)
    return start, end


def _resolve_usage_limit(
    db: Session,
    *,
    organisation_id: int,
    quota_key: str,
    user_id: int | None = None,
):
    if user_id is not None:
        usage_limit = limit_tracking_crud.get_usage_limit(
            db,
            user_id=user_id,
            organisation_id=organisation_id,
            limit_type=quota_key,
        )
        if usage_limit is not None:
            return usage_limit
    return limit_tracking_crud.get_usage_limit(
        db,
        user_id=None,
        organisation_id=organisation_id,
        limit_type=quota_key,
    )


def _cache_key_for_org(organisation_id: int) -> str:
    return f"entitlements:summary:{organisation_id}"


def invalidate_entitlement_cache(organisation_id: int) -> None:
    entitlement_cache.invalidate(_cache_key_for_org(organisation_id))


def resolve_entitlements(db: Session, organisation_id: int) -> EntitlementSnapshot:
    organisation = organisation_crud.get_organisation_by_id(db, organisation_id)
    if not organisation:
        raise NotFoundError("Organisation not found")

    plan = PLAN_DEFINITIONS[_normalize_plan_code(organisation.plan_code)]
    return EntitlementSnapshot(
        organisation_id=organisation.id,
        plan_code=plan.code,
        subscription_status=organisation.subscription_status,
        trial_ends_at=organisation.trial_ends_at,
        features=plan.features,
        quotas=dict(plan.quotas),
    )


def assert_subscription_active(entitlements: EntitlementSnapshot) -> EntitlementSnapshot:
    if entitlements.subscription_active:
        return entitlements
    raise SubscriptionInactiveError(
        details={
            "organisation_id": entitlements.organisation_id,
            "plan_code": entitlements.plan_code,
            "subscription_status": entitlements.subscription_status,
            "trial_ends_at": entitlements.trial_ends_at.isoformat()
            if entitlements.trial_ends_at
            else None,
        }
    )


def ensure_feature_access(
    db: Session, *, organisation_id: int, feature: str
) -> EntitlementSnapshot:
    entitlements = assert_subscription_active(resolve_entitlements(db, organisation_id))
    if feature in entitlements.features:
        return entitlements
    raise FeatureNotAvailableError(
        details={
            "feature": feature,
            "organisation_id": organisation_id,
            "plan_code": entitlements.plan_code,
        }
    )


def resolve_quota(
    db: Session,
    *,
    organisation_id: int,
    quota_key: str,
    user_id: int | None = None,
) -> ResolvedQuota:
    entitlements = assert_subscription_active(resolve_entitlements(db, organisation_id))
    usage_limit = _resolve_usage_limit(
        db, organisation_id=organisation_id, quota_key=quota_key, user_id=user_id
    )

    limit_value = entitlements.quotas.get(quota_key)
    period = "monthly" if limit_value is not None else None

    if usage_limit is not None and _normalize_bool_string(usage_limit.is_active):
        limit_value = usage_limit.limit_value
        period = usage_limit.period

    current_usage = 0.0
    if usage_limit is not None and period is not None:
        period_start, period_end = _period_bounds(period)
        usage_record = limit_tracking_crud.get_limit_usage_record_for_period(
            db,
            usage_limit_id=usage_limit.id,
            period_start=period_start,
            period_end=period_end,
        )
        if usage_record is not None:
            current_usage = float(usage_record.current_usage)

    remaining = None if limit_value is None else max(float(limit_value) - current_usage, 0.0)
    return ResolvedQuota(
        quota_key=quota_key,
        limit_value=None if limit_value is None else float(limit_value),
        period=period,
        current_usage=current_usage,
        remaining=remaining,
        usage_limit_id=getattr(usage_limit, "id", None),
    )


def assert_quota_available(
    db: Session,
    *,
    organisation_id: int,
    quota_key: str,
    units: float = 1.0,
    user_id: int | None = None,
) -> ResolvedQuota:
    quota = resolve_quota(
        db,
        organisation_id=organisation_id,
        quota_key=quota_key,
        user_id=user_id,
    )
    if quota.limit_value is None:
        return quota
    if quota.current_usage + units <= quota.limit_value:
        return quota
    raise QuotaExceededError(
        details={
            "organisation_id": organisation_id,
            "quota_key": quota_key,
            "limit": quota.limit_value,
            "current_usage": quota.current_usage,
            "requested_units": units,
            "remaining": quota.remaining,
            "period": quota.period,
        }
    )


def _resolve_unit_price(
    db: Session, *, organisation_id: int, plan_code: str, meter_key: str
) -> float:
    billing_plan = billing_crud.get_active_billing_plan(
        db, organisation_id=organisation_id, plan_code=plan_code
    ) or billing_crud.get_active_billing_plan(db, organisation_id=organisation_id)
    if billing_plan is not None:
        return float(billing_plan.price_per_unit or 0.0)
    return float(PLAN_DEFINITIONS[plan_code].unit_prices.get(meter_key, 0.0))


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _build_usage_metrics(
    db: Session,
    *,
    organisation_id: int,
    period_start: datetime,
    period_end: datetime,
) -> list[dict[str, object]]:
    usage_events = usage_crud.list_usage_events(
        db,
        organisation_id=organisation_id,
        offset=0,
        limit=1000,
    )
    billing_records = billing_crud.list_billing_records(
        db,
        organisation_id=organisation_id,
        offset=0,
        limit=1000,
    )

    usage_totals: dict[str, float] = {}
    for event in usage_events:
        recorded_at = _as_utc(event.recorded_at)
        if recorded_at < period_start or recorded_at >= period_end:
            continue
        usage_totals[event.event_type] = usage_totals.get(event.event_type, 0.0) + float(
            event.units
        )

    amounts_by_event_type: dict[str, dict[str, float]] = {}
    usage_event_lookup = {event.id: event for event in usage_events}
    for record in billing_records:
        created_at = _as_utc(record.created_at)
        if created_at < period_start or created_at >= period_end:
            continue
        event = usage_event_lookup.get(record.usage_event_id)
        if event is None:
            continue
        metrics = amounts_by_event_type.setdefault(
            event.event_type,
            {"pending_amount": 0.0, "billed_amount": 0.0},
        )
        amount = float(record.amount or 0.0)
        if str(record.status).strip().lower() == "paid":
            metrics["billed_amount"] += amount
        else:
            metrics["pending_amount"] += amount

    all_keys = sorted(set(usage_totals) | set(amounts_by_event_type))
    return [
        {
            "event_type": event_type,
            "total_units": usage_totals.get(event_type, 0.0),
            "pending_amount": round(
                amounts_by_event_type.get(event_type, {}).get("pending_amount", 0.0), 2
            ),
            "billed_amount": round(
                amounts_by_event_type.get(event_type, {}).get("billed_amount", 0.0), 2
            ),
        }
        for event_type in all_keys
    ]


def build_entitlement_summary(
    db: Session, *, organisation_id: int
) -> dict[str, object]:
    cache_key = _cache_key_for_org(organisation_id)
    cached = entitlement_cache.get(cache_key)
    if cached is not None:
        return cached

    entitlements = resolve_entitlements(db, organisation_id)
    billing_plan = billing_crud.get_active_billing_plan(
        db, organisation_id=organisation_id, plan_code=entitlements.plan_code
    ) or billing_crud.get_active_billing_plan(db, organisation_id=organisation_id)
    subscription_active = entitlements.subscription_active

    quotas: list[dict[str, object]] = []
    for quota_key in METERED_RESOURCES:
        feature_name = "enrichment" if quota_key == "enrichment_lookups" else "fraud_detection"
        feature_enabled = feature_name in entitlements.features and subscription_active
        if feature_enabled:
            quota = resolve_quota(db, organisation_id=organisation_id, quota_key=quota_key)
            quotas.append(
                {
                    "quota_key": quota_key,
                    "feature_enabled": True,
                    "limit": quota.limit_value,
                    "current_usage": quota.current_usage,
                    "remaining": quota.remaining,
                    "period": quota.period,
                }
            )
        else:
            quotas.append(
                {
                    "quota_key": quota_key,
                    "feature_enabled": False,
                    "limit": 0.0,
                    "current_usage": 0.0,
                    "remaining": 0.0,
                    "period": None,
                }
            )

    period_start, period_end = _monthly_bounds()
    blocked_features = (
        sorted(ALL_FEATURES)
        if not subscription_active
        else sorted(ALL_FEATURES - entitlements.features)
    )
    payload = {
        "organisation_id": organisation_id,
        "plan": {
            "code": entitlements.plan_code,
            "name": billing_plan.name if billing_plan is not None else entitlements.plan_code.title(),
            "price_per_unit": float(getattr(billing_plan, "price_per_unit", 0.0) or 0.0),
            "currency": getattr(billing_plan, "currency", "USD") or "USD",
            "billing_interval": getattr(billing_plan, "billing_interval", "monthly")
            or "monthly",
            "is_active": bool(getattr(billing_plan, "is_active", True)),
            "subscription_status": entitlements.subscription_status,
            "trial_ends_at": _serialize_datetime(entitlements.trial_ends_at),
        },
        "quotas": quotas,
        "blocked_features": blocked_features,
        "usage_metrics": _build_usage_metrics(
            db,
            organisation_id=organisation_id,
            period_start=period_start,
            period_end=period_end,
        ),
        "cached_at": datetime.now(UTC).isoformat(),
    }
    entitlement_cache.set(cache_key, payload, ENTITLEMENT_CACHE_TTL_SECONDS)
    return payload


def record_consumption(
    db: Session,
    *,
    organisation_id: int,
    user_id: int,
    meter_key: str,
    units: float = 1.0,
    currency: str = "USD",
    description: str | None = None,
    commit: bool = True,
) -> None:
    user = user_crud.get_user_by_id(db, user_id)
    if not user or user.organisation_id != organisation_id:
        raise NotFoundError("User not found")

    entitlements = assert_subscription_active(resolve_entitlements(db, organisation_id))
    normalized_currency = (currency or "USD").strip().upper()

    try:
        usage_event = usage_crud.create_usage_event(
            db,
            commit=False,
            user_id=user_id,
            organisation_id=organisation_id,
            event_type=meter_key,
            units=units,
            unit_type="request",
            description=description or meter_key.replace("_", " ").title(),
            status="recorded",
        )

        summary_start, summary_end = _monthly_bounds()
        usage_summary = usage_crud.get_usage_summary_for_period(
            db,
            user_id=user_id,
            organisation_id=organisation_id,
            period_start=summary_start,
            period_end=summary_end,
            currency=normalized_currency,
        )
        if usage_summary is None:
            usage_crud.create_usage_summary(
                db,
                commit=False,
                user_id=user_id,
                organisation_id=organisation_id,
                period_start=summary_start,
                period_end=summary_end,
                total_units=units,
                currency=normalized_currency,
            )
        else:
            usage_crud.update_usage_summary(
                db,
                usage_summary,
                commit=False,
                total_units=float(usage_summary.total_units) + units,
            )

        quota = resolve_quota(
            db,
            organisation_id=organisation_id,
            quota_key=meter_key,
            user_id=user_id,
        )
        if quota.limit_value is not None:
            usage_limit = _resolve_usage_limit(
                db,
                organisation_id=organisation_id,
                quota_key=meter_key,
                user_id=user_id,
            )
            if usage_limit is None:
                usage_limit = limit_tracking_crud.create_usage_limit(
                    db,
                    commit=False,
                    user_id=None,
                    organisation_id=organisation_id,
                    limit_type=meter_key,
                    limit_value=quota.limit_value,
                    period=quota.period or "monthly",
                    is_active="true",
                )
            period_start, period_end = _period_bounds(quota.period or "monthly")
            usage_record = limit_tracking_crud.get_limit_usage_record_for_period(
                db,
                usage_limit_id=usage_limit.id,
                period_start=period_start,
                period_end=period_end,
            )
            if usage_record is None:
                limit_tracking_crud.create_limit_usage_record(
                    db,
                    commit=False,
                    usage_limit_id=usage_limit.id,
                    current_usage=units,
                    period_start=period_start,
                    period_end=period_end,
                )
            else:
                limit_tracking_crud.update_limit_usage_record(
                    db,
                    usage_record,
                    commit=False,
                    current_usage=float(usage_record.current_usage) + units,
                    updated_at=datetime.now(UTC),
                )

        unit_price = _resolve_unit_price(
            db,
            organisation_id=organisation_id,
            plan_code=entitlements.plan_code,
            meter_key=meter_key,
        )
        billing_crud.create_billing_record(
            db,
            commit=False,
            user_id=user_id,
            organisation_id=organisation_id,
            usage_event_id=usage_event.id,
            amount=round(units * unit_price, 2),
            currency=normalized_currency,
            status="pending",
            description=description or meter_key.replace("_", " ").title(),
            billing_period_start=summary_start,
            billing_period_end=summary_end,
        )

        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise

    invalidate_entitlement_cache(organisation_id)
