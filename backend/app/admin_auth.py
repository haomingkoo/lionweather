import hmac
import os

from fastapi import Header, HTTPException


def require_admin(secret: str | None) -> None:
    """Raise 403 if the provided secret does not match ADMIN_SECRET env var."""
    expected = os.getenv("ADMIN_SECRET")
    if not expected or not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Secret header")


def admin_header(x_admin_secret: str = Header(default=None, alias="X-Admin-Secret")) -> None:
    require_admin(x_admin_secret)
