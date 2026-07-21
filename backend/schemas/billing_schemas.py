from datetime import datetime
from typing import Any, Optional

from pydantic import ConfigDict, Field

from schemas.api_schemas import PaginatedResponse, StrictSchema


class BillingPlanBase(StrictSchema):
    organisation_id: int
    name: str
    plan_code: str = "starter"
    billing_provider: str = "internal"
    provider_plan_id: Optional[str] = None
    price_per_unit: float = 0.0
    currency: str = "USD"
    billing_interval: str = "monthly"
    is_active: bool = True


class BillingPlanCreate(BillingPlanBase):
    pass


class BillingPlanOut(BillingPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class BillingRecordBase(StrictSchema):
    user_id: int
    organisation_id: int
    usage_event_id: Optional[int] = None
    amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"
    billing_provider: str = "internal"
    invoice_id: Optional[str] = None
    provider_invoice_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    provider_event_id: Optional[str] = None
    description: Optional[str] = None
    billing_period_start: datetime
    billing_period_end: datetime


class BillingRecordCreate(BillingRecordBase):
    pass


class BillingRecordOut(BillingRecordBase):
    id: int
    created_at: datetime
    billed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class BillingPlanListResponse(PaginatedResponse[BillingPlanOut]):
    pass


class BillingRecordListResponse(PaginatedResponse[BillingRecordOut]):
    pass


class BillingGraphQLRequest(StrictSchema):
    query: str
    variables: dict[str, Any] = Field(default_factory=dict)
    operation_name: Optional[str] = None


class SubscriptionMutationInput(StrictSchema):
    action: str
    target_plan_code: Optional[str] = None
    billing_record_id: Optional[int] = None
    reason: Optional[str] = None
    trial_ends_at: Optional[datetime] = None


class SubscriptionMutationResult(StrictSchema):
    organisation_id: int
    action: str
    previous_plan_code: str
    current_plan_code: str
    previous_subscription_status: str
    current_subscription_status: str
    billing_record_id: Optional[int] = None
    changed_at: datetime


class GraphQLErrorExtension(StrictSchema):
    code: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = ""


class GraphQLErrorOut(StrictSchema):
    message: str
    extensions: GraphQLErrorExtension


class BillingPlanSummaryOut(StrictSchema):
    code: str
    name: str
    price_per_unit: float = 0.0
    currency: str = "USD"
    billing_interval: str = "monthly"
    is_active: bool = True
    subscription_status: str
    trial_ends_at: Optional[datetime] = None


class QuotaAllocationOut(StrictSchema):
    quota_key: str
    feature_enabled: bool = True
    limit: Optional[float] = None
    current_usage: float = 0.0
    remaining: Optional[float] = None
    period: Optional[str] = None


class UsageMetricOut(StrictSchema):
    event_type: str
    total_units: float = 0.0
    pending_amount: float = 0.0
    billed_amount: float = 0.0


class BillingEntitlementsOut(StrictSchema):
    organisation_id: int
    plan: BillingPlanSummaryOut
    quotas: list[QuotaAllocationOut]
    blocked_features: list[str]
    usage_metrics: list[UsageMetricOut]
    cached_at: datetime


class RazorpayBillingLinkRequest(StrictSchema):
    customer_external_id: Optional[str] = None
    subscription_external_id: Optional[str] = None


class RazorpayBillingLinkOut(StrictSchema):
    organisation_id: int
    billing_provider: str
    billing_customer_external_id: Optional[str] = None
    billing_subscription_external_id: Optional[str] = None
    updated_at: datetime
