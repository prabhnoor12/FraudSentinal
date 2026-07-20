from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth_dependencies import (
    get_current_org_id,
    get_current_principal,
    get_current_user,
    require_active_subscription,
    require_feature,
    require_scopes,
)
from database import get_db
from schemas.billing_schemas import (
    BillingEntitlementsOut,
    BillingGraphQLRequest,
    BillingPlanCreate,
    BillingPlanListResponse,
    BillingPlanOut,
    BillingRecordListResponse,
    BillingRecordCreate,
    BillingRecordOut,
    GraphQLErrorOut,
    SubscriptionMutationInput,
    SubscriptionMutationResult,
)
from services import billing_service, entitlement_service
from utils.exception_handling_utils import AppException, ForbiddenError, ValidationError
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/billing", tags=["billing"])

ENTITLEMENTS_CACHE_CONTROL = "private, max-age=30"


def _audit_context(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def _require_billing_mutation_actor(
    principal=Depends(get_current_principal),
):
    if principal.user and principal.user.role != "admin":
        raise ForbiddenError("Only organisation admins can manage subscriptions")
    return principal


def _graphql_error_response(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    error = GraphQLErrorOut(
        message=exc.message,
        extensions={
            "code": exc.error_code,
            "details": exc.details,
            "request_id": request_id,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": None, "errors": [error.model_dump()]},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@router.get(
    "/plans",
    response_model=BillingPlanListResponse,
    summary="List billing plans",
    description="Returns billing plans visible to the authenticated organisation using the standard v1 paginated list envelope.",
    dependencies=[
        Depends(require_scopes("billing:read")),
        Depends(require_active_subscription()),
        Depends(require_feature("billing")),
    ],
)
def list_billing_plans(
    request: Request,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = billing_service.list_billing_plans_service(
        db,
        organisation_id=org_id,
        is_active=is_active,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.post(
    "/plans",
    response_model=BillingPlanOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create billing plan",
    description="Creates a billing plan in the authenticated organisation.",
    dependencies=[
        Depends(require_scopes("billing:write")),
        Depends(require_active_subscription()),
        Depends(require_feature("billing")),
    ],
)
def create_billing_plan(
    payload: BillingPlanCreate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    payload.organisation_id = org_id
    return billing_service.create_billing_plan_service(db, payload)


@router.get(
    "/records",
    response_model=BillingRecordListResponse,
    summary="List billing records",
    description="Returns billing records for the authenticated organisation using the standard v1 paginated list envelope.",
    dependencies=[
        Depends(require_scopes("billing:read")),
        Depends(require_active_subscription()),
        Depends(require_feature("billing")),
    ],
)
def list_billing_records(
    request: Request,
    user_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = billing_service.list_billing_records_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        status=status,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.post(
    "/records",
    response_model=BillingRecordOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create billing record",
    description="Creates a billing record in the authenticated organisation. Public clients should send an Idempotency-Key header.",
    dependencies=[
        Depends(require_scopes("billing:write")),
        Depends(require_active_subscription()),
        Depends(require_feature("billing")),
    ],
)
def create_billing_record(
    payload: BillingRecordCreate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    payload.organisation_id = org_id
    return billing_service.create_billing_record_service(db, payload)


@router.post(
    "/graphql",
    summary="Billing GraphQL mutations",
    description="Supports the explicit updateOrganisationSubscription GraphQL mutation for subscription lifecycle changes.",
    dependencies=[Depends(require_scopes("billing:write"))],
)
def billing_graphql(
    request: Request,
    payload: BillingGraphQLRequest,
    org_id: int = Depends(get_current_org_id),
    principal=Depends(_require_billing_mutation_actor),
    db: Session = Depends(get_db),
):
    query = payload.query.strip()
    if "mutation" not in query or "updateOrganisationSubscription" not in query:
        return _graphql_error_response(
            request,
            ValidationError(
                "Only the updateOrganisationSubscription mutation is supported"
            ),
        )

    raw_input = payload.variables.get("input")
    if not isinstance(raw_input, dict):
        return _graphql_error_response(
            request,
            ValidationError("GraphQL variables.input is required for this mutation"),
        )

    try:
        mutation_input = SubscriptionMutationInput.model_validate(raw_input)
        result = billing_service.update_subscription_service(
            db,
            principal=principal,
            organisation_id=org_id,
            payload=mutation_input,
            **_audit_context(request),
        )
    except AppException as exc:
        return _graphql_error_response(request, exc)

    response = SubscriptionMutationResult.model_validate(result)
    return {
        "data": {
            "updateOrganisationSubscription": {
                "organisationId": response.organisation_id,
                "action": response.action,
                "previousPlanCode": response.previous_plan_code,
                "currentPlanCode": response.current_plan_code,
                "previousSubscriptionStatus": response.previous_subscription_status,
                "currentSubscriptionStatus": response.current_subscription_status,
                "billingRecordId": response.billing_record_id,
                "changedAt": response.changed_at.isoformat(),
            }
        }
    }


@router.get(
    "/entitlements",
    response_model=BillingEntitlementsOut,
    summary="Get billing entitlements",
    description="Returns the current plan, remaining quota allocations, blocked features, and current-period billable usage metrics for the authenticated organisation.",
    dependencies=[Depends(require_scopes("billing:read"))],
)
def get_billing_entitlements(
    response: Response,
    org_id: int = Depends(get_current_org_id),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = entitlement_service.build_entitlement_summary(
        db,
        organisation_id=org_id,
    )
    response.headers["Cache-Control"] = ENTITLEMENTS_CACHE_CONTROL
    return BillingEntitlementsOut.model_validate(payload)
