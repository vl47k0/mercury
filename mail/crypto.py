"""Symmetric encryption for stored mail-account passwords.

Uses Fernet with a key from ``MAIL_ENCRYPTION_KEY`` (a urlsafe-base64 32-byte
key), falling back to one derived from ``DJANGO_SECRET_KEY`` so the service runs
without extra config. Set a dedicated key in production so rotating the Django
secret doesn't strand stored passwords.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    key = getattr(settings, "MAIL_ENCRYPTION_KEY", "") or ""
    if not key:
        # Derive a stable 32-byte urlsafe key from the Django secret.
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
