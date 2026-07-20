# Debug Session: password-reset-timezone

Status: OPEN

Symptom:
- `POST /auth/password-reset/confirm` fails with `TypeError: can't compare offset-naive and offset-aware datetimes`

Hypotheses:
- `reset_token.expires_at` is stored as a naive datetime from the database while the code compares against `datetime.now(UTC)`.
- The reset-token creation path writes naive datetimes, but the confirm path expects timezone-aware datetimes.
- SQLAlchemy/database configuration strips timezone info even if Python code creates aware datetimes.
- Only the confirm path is inconsistent; other auth code uses naive UTC comparisons or normalizes values first.

Evidence Collected:
- Runtime stack trace shows failure at `services/auth_service.py` in `confirm_password_reset`.

Next Step:
- Inspect reset-token model and auth service datetime handling, then normalize the comparison to one consistent form.
