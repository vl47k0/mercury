"""Derive contacts from a user's mail and push them to the contacts service.

Scans stored messages for correspondents (senders + recipients), aggregates a
message count + last-seen per email, and upserts each into the owner's address
book via the contacts ingest API (service-key). The owner's own mailbox
address(es) are excluded so you don't become your own contact.
"""
from __future__ import annotations

import json
import logging
import urllib.request

from django.conf import settings

from .models import MailAccount, StoredEmail

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(
        getattr(settings, "CONTACTS_INGEST_URL", "")
        and getattr(settings, "CONTACTS_SERVICE_KEY", "")
    )


def _post(payload: dict) -> dict | None:
    base = settings.CONTACTS_INGEST_URL.rstrip("/")
    req = urllib.request.Request(
        base + "/api/v1/ingest/",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Service-Key": settings.CONTACTS_SERVICE_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _iter_addrs(value):
    for a in value or []:
        if isinstance(a, dict):
            yield (a.get("email") or "").strip().lower(), (a.get("name") or "").strip()
        elif a:
            yield str(a).strip().lower(), ""


def sync_owner(owner: str) -> dict:
    if not _configured():
        return {"ok": False, "error": "contacts connector not configured", "pushed": 0}
    own = {
        e.lower()
        for e in MailAccount.objects.filter(owner=owner).values_list("email", flat=True)
        if e
    }
    people: dict[str, dict] = {}  # email -> {name, count, last_seen}

    def note(email: str, name: str, when):
        if not email or "@" not in email or email in own:
            return
        p = people.setdefault(email, {"name": "", "count": 0, "last_seen": None})
        p["count"] += 1
        if name and not p["name"]:
            p["name"] = name
        if when and (p["last_seen"] is None or when > p["last_seen"]):
            p["last_seen"] = when

    for m in StoredEmail.objects.filter(owner=owner, is_deleted=False).iterator():
        when = m.sent_at or m.received_at
        note((m.from_email or "").strip().lower(), m.from_name, when)
        for email, name in _iter_addrs(m.to):
            note(email, name, when)
        for email, name in _iter_addrs(m.cc):
            note(email, name, when)

    pushed = errors = 0
    for email, info in people.items():
        try:
            _post(
                {
                    "owner": owner,
                    "email": email,
                    "name": info["name"],
                    "source": "mail",
                    "message_count": info["count"],
                    "last_seen": info["last_seen"].isoformat() if info["last_seen"] else None,
                }
            )
            pushed += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning("contacts_push_failed", extra={"email": email, "error": str(exc)[:200]})
    return {"ok": True, "people": len(people), "pushed": pushed, "errors": errors}
