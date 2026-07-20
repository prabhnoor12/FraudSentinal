from __future__ import annotations

import json
from datetime import UTC, datetime

from utils.security_utils import generate_hmac_signature


def build_webhook_signature(
    payload: dict, *, secret: str, timestamp: str | None = None
) -> dict[str, str]:
    """Return standard webhook signature headers for an outgoing event."""
    webhook_timestamp = timestamp or str(int(datetime.now(UTC).timestamp()))
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signed_payload = f"{webhook_timestamp}.{serialized}"
    signature = generate_hmac_signature(signed_payload, secret)
    return {
        "X-FraudSentinal-Timestamp": webhook_timestamp,
        "X-FraudSentinal-Signature": signature,
    }


def verify_webhook_signature(
    payload: dict,
    *,
    secret: str,
    timestamp: str,
    signature: str,
) -> bool:
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    expected = generate_hmac_signature(f"{timestamp}.{serialized}", secret)
    return expected == signature
