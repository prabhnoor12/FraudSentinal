from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from database import get_db
from services import razorpay_billing_service
from utils.exception_handling_utils import ValidationError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/razorpay",
    status_code=status.HTTP_200_OK,
    summary="Receive Razorpay webhooks",
    description="Processes signed Razorpay payment and subscription webhooks and synchronizes billing state into the platform.",
)
async def receive_razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("x-razorpay-event-id") or request.headers.get(
        "X-Razorpay-Event-Id"
    )
    if not event_id:
        raise ValidationError(
            "Razorpay webhook event ID is required",
            details={"header": "x-razorpay-event-id"},
        )

    razorpay_billing_service.verify_razorpay_signature(
        raw_body=raw_body,
        signature=signature,
    )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid Razorpay webhook JSON payload") from exc

    return razorpay_billing_service.process_razorpay_webhook(
        db,
        raw_body=raw_body,
        payload=payload,
        event_id=event_id,
        request=request,
    )
