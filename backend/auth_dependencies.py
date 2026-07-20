from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from auth import api_key_header, oauth2_scheme
from database import get_db
from services import auth_service, entitlement_service
from utils.exception_handling_utils import (
    FeatureNotAvailableError,
    ForbiddenError,
    UnauthorizedError,
)


@dataclass
class AuthenticatedPrincipal:
    principal_type: str
    subject_id: str
    organisation_id: int | None
    scopes: set[str] = field(default_factory=set)
    user: object | None = None
    service_account: object | None = None
    api_key: object | None = None

    @property
    def is_user(self) -> bool:
        return self.principal_type == "user"

    @property
    def is_service_account(self) -> bool:
        return self.principal_type == "service_account"


def get_current_principal(
    bearer_token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> AuthenticatedPrincipal:
    principal = auth_service.get_authenticated_principal(
        db, bearer_token=bearer_token, api_key=api_key
    )
    if principal is None:
        raise UnauthorizedError("Authentication credentials were not provided")
    return principal


def get_current_user(principal: AuthenticatedPrincipal = Depends(get_current_principal)):
    if not principal.user:
        raise ForbiddenError("This endpoint requires an interactive user session")
    return principal.user


def get_current_org_id(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> int:
    if principal.organisation_id is None:
        raise ForbiddenError("Principal is not assigned to an organisation")
    return int(principal.organisation_id)


def require_scopes(*required_scopes: str) -> Callable:
    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if principal.is_user:
            return principal

        if "*" in principal.scopes:
            return principal

        missing = [scope for scope in required_scopes if scope not in principal.scopes]
        if missing:
            raise ForbiddenError(
                "Missing required API scope",
                details={"required_scopes": required_scopes, "missing_scopes": missing},
            )
        return principal

    return dependency


def get_current_entitlements(
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
) -> entitlement_service.EntitlementSnapshot:
    return entitlement_service.resolve_entitlements(db, org_id)


def require_active_subscription() -> Callable:
    def dependency(
        entitlements: entitlement_service.EntitlementSnapshot = Depends(
            get_current_entitlements
        ),
    ) -> entitlement_service.EntitlementSnapshot:
        return entitlement_service.assert_subscription_active(entitlements)

    return dependency


def require_feature(feature: str) -> Callable:
    def dependency(
        entitlements: entitlement_service.EntitlementSnapshot = Depends(
            get_current_entitlements
        ),
    ) -> entitlement_service.EntitlementSnapshot:
        entitlement_service.assert_subscription_active(entitlements)
        if feature not in entitlements.features:
            raise FeatureNotAvailableError(
                details={
                    "feature": feature,
                    "organisation_id": entitlements.organisation_id,
                    "plan_code": entitlements.plan_code,
                }
            )
        return entitlements

    return dependency


def require_quota(quota_key: str, *, units: float = 1.0) -> Callable:
    def dependency(
        org_id: int = Depends(get_current_org_id),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
        db: Session = Depends(get_db),
    ) -> entitlement_service.ResolvedQuota:
        return entitlement_service.assert_quota_available(
            db,
            organisation_id=org_id,
            quota_key=quota_key,
            units=units,
            user_id=getattr(principal.user, "id", None),
        )

    return dependency
