"""Authentication for mercury — trust the authd edge.

In the live cluster mercury runs as a ClusterIP service reachable only through
the authd nginx edge. authd validates the phoebe JWT (RS256/JWKS) and forwards
the verified claims as X-JWT-* request headers via proxy_set_header, which
OVERWRITES any client-supplied X-JWT-* headers. mercury therefore does no token
decoding of its own for edge traffic: it trusts those headers.

For local development the SimpleJWT ``JWTAuthentication`` class remains wired in
settings (see DEFAULT_AUTHENTICATION_CLASSES), so ``/api/token/`` + a Bearer
token still work when there is no edge in front.
"""
from __future__ import annotations

from rest_framework.authentication import BaseAuthentication


class EdgeUser:
    """End-user identity built from authd's X-JWT-* claim headers.

    Not a database row — mercury's RAG endpoint only needs an authenticated
    principal, keyed off ``id`` (the phoebe ``sub``). Admin-only endpoints
    (accounts) see ``is_staff = False`` and will 403 for edge callers, which is
    intended: user/document administration is done via local dev or rigel.
    """

    is_staff = False
    is_superuser = False

    def __init__(self, **entries):
        self.__dict__.update(entries)

    @property
    def id(self):
        raw = getattr(self, "sub", None) or getattr(self, "user_id", None)
        return str(raw) if raw is not None else None

    @property
    def pk(self):
        return self.id

    @property
    def is_authenticated(self):
        return self.id is not None

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return self.id is None

    def get_username(self):
        return getattr(self, "email", None) or self.id

    def __str__(self):
        return f"EdgeUser({self.id})"


class EdgeJWTAuthentication(BaseAuthentication):
    """Trust the claim headers injected by the authd edge.

    Reads:
      X-JWT-Sub    -> user identity (phoebe sub)
      X-JWT-Email  -> email
      X-JWT-Secret -> per-user opaque secret, if present

    Returns None (anonymous) when no X-JWT-Sub header is present, letting DRF
    fall through to the next authentication class (SimpleJWT for local dev).
    """

    def authenticate(self, request):
        sub = request.META.get("HTTP_X_JWT_SUB")
        if not sub:
            return None
        user = EdgeUser(
            sub=sub,
            user_id=sub,
            email=request.META.get("HTTP_X_JWT_EMAIL", ""),
            secret=request.META.get("HTTP_X_JWT_SECRET", ""),
        )
        return user, None


class ServiceUser:
    """A backend worker authenticated via the shared service key."""

    is_staff = False
    is_superuser = False

    def __init__(self, name: str = "worker"):
        self.name = name

    @property
    def id(self):
        return self.name

    @property
    def pk(self):
        return self.name

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return True

    def __str__(self):
        return f"ServiceUser({self.name})"


class ServiceKeyAuthentication(BaseAuthentication):
    """Authenticate the CLIP worker via a shared X-Mercury-Key header
    (compared against MERCURY_SERVICE_KEY). Absent header -> None (fall
    through); present-but-wrong -> hard fail."""

    def authenticate(self, request):
        import secrets

        from django.conf import settings
        from rest_framework.exceptions import AuthenticationFailed

        key = request.META.get("HTTP_X_MERCURY_KEY")
        if not key:
            return None
        expected = getattr(settings, "MERCURY_SERVICE_KEY", "") or ""
        if not expected or not secrets.compare_digest(key, expected):
            raise AuthenticationFailed("Invalid service key")
        return ServiceUser(), None

    def authenticate_header(self, request):
        return "X-Mercury-Key"
