"""IMAP inbound fetch for MailAccounts.

Connects to the user's mailbox, pulls messages newer than the last-seen UID per
folder (using BODY.PEEK so nothing is marked read on the server), and ingests
each via services.ingest_eml (deduped by Message-ID). Read-only mirror — we
never modify the remote mailbox.
"""
from __future__ import annotations

import imaplib
import logging

from django.utils import timezone

from . import services

logger = logging.getLogger(__name__)

# Cap per folder per run so a first sync of a huge mailbox can't run away.
MAX_PER_FOLDER = 500


def _connect(account) -> imaplib.IMAP4:
    if account.imap_ssl:
        m = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
    else:
        m = imaplib.IMAP4(account.imap_host, account.imap_port)
    m.login(account.login, account.get_password())
    return m


def _extract_raw(fetch_data) -> bytes | None:
    for part in fetch_data:
        if isinstance(part, tuple) and len(part) == 2 and isinstance(part[1], (bytes, bytearray)):
            return bytes(part[1])
    return None


def fetch_new(account) -> dict:
    """Pull new messages for one account. Returns a small result summary."""
    fetched, created = 0, 0
    last_uid = dict(account.last_uid or {})
    try:
        m = _connect(account)
        try:
            for folder in account.poll_folders:
                try:
                    typ, _ = m.select(f'"{folder}"', readonly=True)
                    if typ != "OK":
                        continue
                    since = int(last_uid.get(folder, 0))
                    typ, data = m.uid("search", None, f"UID {since + 1}:*")
                    if typ != "OK" or not data or not data[0]:
                        continue
                    uids = [int(u) for u in data[0].split() if int(u) > since]
                    uids.sort()
                    highest = since
                    for uid in uids[:MAX_PER_FOLDER]:
                        typ, msg = m.uid("fetch", str(uid), "(BODY.PEEK[])")
                        if typ != "OK":
                            continue
                        raw = _extract_raw(msg)
                        if not raw:
                            continue
                        _, was_new = services.ingest_eml(
                            account.owner, raw, source="imap", mailbox=folder
                        )
                        fetched += 1
                        created += 1 if was_new else 0
                        highest = max(highest, uid)
                    last_uid[folder] = highest
                except Exception as exc:  # noqa: BLE001 — isolate per-folder failures
                    logger.warning(
                        "imap_folder_failed",
                        extra={"folder": folder, "error": str(exc)[:200]},
                    )
        finally:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass
        account.last_uid = last_uid
        account.last_synced_at = timezone.now()
        account.last_error = ""
        account.save(update_fields=["last_uid", "last_synced_at", "last_error"])
        return {"ok": True, "fetched": fetched, "new": created}
    except Exception as exc:  # noqa: BLE001
        account.last_error = str(exc)[:400]
        account.last_synced_at = timezone.now()
        account.save(update_fields=["last_error", "last_synced_at"])
        logger.warning("imap_sync_failed", extra={"owner": account.owner, "error": account.last_error})
        return {"ok": False, "error": account.last_error, "fetched": fetched, "new": created}


def test_imap(account) -> dict:
    """Verify IMAP login + INBOX select without fetching."""
    try:
        m = _connect(account)
        try:
            typ, data = m.select("INBOX", readonly=True)
            count = int(data[0]) if typ == "OK" and data and data[0] else 0
            return {"ok": True, "inbox_count": count}
        finally:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}
