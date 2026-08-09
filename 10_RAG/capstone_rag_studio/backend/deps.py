"""Acting_Principal extraction — validated before any other request processing (Req 14.3).

Every route depends on :func:`get_principal`. FastAPI resolves dependencies before a
route's body executes, so a missing/invalid principal always raises before any
data-shape error inside the route itself (Req 14.6, 14.7).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header

from rag.interfaces import Principal


class AuthError(Exception):
    """Raised when no Acting_Principal can be established for the request (Req 11.7)."""

    def __init__(self, message: str = "Missing Acting_Principal: the 'X-Principal-Id' header is required."):
        super().__init__(message)


def get_principal(
    x_principal_id: Optional[str] = Header(default=None, alias="X-Principal-Id"),
    x_principal_roles: Optional[str] = Header(default=None, alias="X-Principal-Roles"),
) -> Principal:
    if not x_principal_id:
        raise AuthError()
    roles = [r.strip() for r in x_principal_roles.split(",") if r.strip()] if x_principal_roles else []
    return Principal(id=x_principal_id, roles=roles)
