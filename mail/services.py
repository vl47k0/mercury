"""Ingest raw email into StoredEmail. Idempotent per (owner, message_id)."""
from __future__ import annotations

from django.contrib.postgres.search import SearchVector
from django.db import IntegrityError

from . import parser
from .models import StoredEmail

SEARCH_FIELDS = ("subject", "from_name", "from_email", "body_preview", "text_body")


def refresh_search_vector(pk) -> None:
    StoredEmail.objects.filter(pk=pk).update(
        search_vector=SearchVector(*SEARCH_FIELDS, config="simple")
    )


def ingest_eml(
    owner: str, raw: bytes, *, source: str = "eml", mailbox: str = "", batch_id=None
) -> tuple[StoredEmail, bool]:
    """Returns (email, created). Deduped per (owner, message_id)."""
    fields = parser.parse_eml(raw, owner, source=source, mailbox=mailbox)
    existing = StoredEmail.objects.filter(
        owner=owner, message_id=fields["message_id"]
    ).first()
    if existing:
        return existing, False
    if batch_id:
        fields["import_batch_id"] = batch_id
    obj = StoredEmail(**fields)
    try:
        obj.save()
    except IntegrityError:
        return StoredEmail.objects.get(owner=owner, message_id=fields["message_id"]), False
    refresh_search_vector(obj.id)
    return obj, True
