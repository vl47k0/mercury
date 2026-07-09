"""Push stored mail into the orion RAG corpus (owner-scoped).

Each message becomes an orion document (source_type='mail') deep-linked back to
the odeon Mail view. orion dedups by (owner, source_type, external_id) + checksum,
so re-running only embeds new/changed messages. Best-effort: a push failure for
one message is logged and skipped, never aborting the batch.
"""
from __future__ import annotations

import json
import logging
import urllib.request

from django.conf import settings

from .models import StoredEmail

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(getattr(settings, "ORION_INGEST_URL", "") and getattr(settings, "ORION_SERVICE_KEY", ""))


def _post(path: str, payload: dict) -> dict | None:
    base = settings.ORION_INGEST_URL.rstrip("/")
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Service-Key": settings.ORION_SERVICE_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _addrs(value) -> str:
    out = []
    for a in value or []:
        if isinstance(a, dict):
            name, email = a.get("name", ""), a.get("email", "")
            out.append(f"{name} <{email}>".strip() if name else email)
        else:
            out.append(str(a))
    return ", ".join(x for x in out if x)


def _mail_text(m: StoredEmail) -> str:
    lines = [f"Subject: {m.subject or '(no subject)'}"]
    frm = f"{m.from_name} <{m.from_email}>".strip() if m.from_name else m.from_email
    if frm:
        lines.append(f"From: {frm}")
    to = _addrs(m.to)
    if to:
        lines.append(f"To: {to}")
    when = m.sent_at or m.received_at
    if when:
        lines.append(f"Date: {when.isoformat()}")
    if m.mailbox:
        lines.append(f"Folder: {m.mailbox}")
    lines.append("")
    lines.append(m.best_body or m.body_preview or "")
    return "\n".join(lines).strip()


def push_message(m: StoredEmail) -> bool:
    """Push one message; returns True if orion (re)ingested it."""
    res = _post(
        "/api/ingest/",
        {
            "owner": m.owner,
            "source_type": "mail",
            "source_uri": f"/mail?id={m.id}",
            "title": (m.subject or "(no subject)")[:200],
            "external_id": str(m.id),
            "text": _mail_text(m),
        },
    )
    return bool(res and res.get("ingested"))


def sync_owner(owner: str, limit: int | None = None) -> dict:
    if not _configured():
        return {"ok": False, "error": "orion connector not configured", "pushed": 0}
    qs = StoredEmail.objects.filter(owner=owner, is_deleted=False)
    if limit:
        qs = qs[:limit]
    pushed = errors = seen = 0
    ids: list[str] = []
    for m in qs.iterator():
        seen += 1
        ids.append(str(m.id))
        try:
            if push_message(m):
                pushed += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning("orion_push_failed", extra={"id": str(m.id), "error": str(exc)[:200]})
    # Prune orion docs for messages that no longer exist (deleted/expunged).
    try:
        _post("/api/ingest/reconcile/", {"owner": owner, "source_type": "mail", "external_ids": ids})
    except Exception as exc:  # noqa: BLE001
        logger.warning("orion_reconcile_failed", extra={"error": str(exc)[:200]})
    return {"ok": True, "seen": seen, "pushed": pushed, "errors": errors}
