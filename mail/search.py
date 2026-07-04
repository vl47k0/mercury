"""Structured filters + tsvector text search for the mailbox list."""
from __future__ import annotations

from datetime import datetime, timezone

from django.contrib.postgres.search import SearchQuery
from django.db.models import QuerySet
from django.db.models.functions import Coalesce

TRUE = {"1", "true", "yes", "on"}


def _dt(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def text_query(params):
    q = (params.get("q") or "").strip()
    return SearchQuery(q, config="simple", search_type="websearch") if q else None


def apply_filters(qs: QuerySet, params) -> QuerySet:
    # Deleted hidden unless explicitly requested.
    if (params.get("deleted") or "").lower() not in TRUE:
        qs = qs.filter(is_deleted=False)
    for flag in ("is_read", "is_archived", "is_spam", "has_attachments"):
        val = params.get(flag)
        if val is not None and val != "":
            qs = qs.filter(**{flag: val.lower() in TRUE})
    if params.get("from"):
        qs = qs.filter(from_email__icontains=params["from"])
    # A specific mailbox (e.g. "sent") shows only that; otherwise the default
    # view is received mail — the "sent" copies are excluded.
    if params.get("mailbox"):
        qs = qs.filter(mailbox=params["mailbox"])
    elif (params.get("include_sent") or "").lower() not in TRUE:
        qs = qs.exclude(mailbox="sent")
    if params.get("list_id"):
        qs = qs.filter(list_id__icontains=params["list_id"])
    if params.get("label"):
        qs = qs.filter(labels__contains=[params["label"]])

    qs = qs.annotate(sort_ts=Coalesce("sent_at", "received_at"))
    if (df := _dt(params.get("after", ""))):
        qs = qs.filter(sort_ts__gte=df)
    if (dt := _dt(params.get("before", ""))):
        qs = qs.filter(sort_ts__lte=dt)

    sq = text_query(params)
    if sq is not None:
        qs = qs.filter(search_vector=sq)
    return qs
