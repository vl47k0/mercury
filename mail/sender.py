"""Compose + send. Builds an RFC822 message, relays it via SMTP when
configured, and always stores a copy in the owner's `sent` mailbox (so the UI
is complete even before an SMTP relay is wired up). Delivery status is recorded
in the stored message's metadata.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from django.conf import settings

from . import services

logger = logging.getLogger(__name__)


def _emails(addrs) -> list[str]:
    out = []
    for a in addrs or []:
        out.append(a["email"] if isinstance(a, dict) else str(a))
    return [e for e in out if e]


def _smtp_config(account):
    """Return an SMTP dict from the user's account, else the global relay, else None."""
    if account is not None and account.smtp_host:
        return {
            "host": account.smtp_host,
            "port": account.smtp_port,
            "security": account.smtp_security,
            "user": account.login,
            "password": account.get_password(),
        }
    if settings.SMTP_HOST:
        security = "ssl" if settings.SMTP_SSL else ("starttls" if settings.SMTP_TLS else "none")
        return {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "security": security,
            "user": settings.SMTP_USER,
            "password": settings.SMTP_PASSWORD,
        }
    return None


def _connect_smtp(cfg):
    if cfg["security"] == "ssl":
        srv = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30)
    else:
        srv = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
        if cfg["security"] == "starttls":
            srv.starttls()
    if cfg["user"]:
        srv.login(cfg["user"], cfg["password"])
    return srv


def test_smtp(account) -> dict:
    """Verify SMTP connect + auth without sending."""
    cfg = _smtp_config(account)
    if not cfg:
        return {"ok": False, "error": "No SMTP host configured."}
    try:
        srv = _connect_smtp(cfg)
        srv.noop()
        srv.quit()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}


def _fmt(addrs) -> str:
    parts = []
    for a in addrs or []:
        if isinstance(a, dict):
            parts.append(formataddr((a.get("name", ""), a["email"])))
        else:
            parts.append(str(a))
    return ", ".join(parts)


def send_message(
    owner: str,
    *,
    from_email: str,
    from_name: str = "",
    to,
    cc=None,
    bcc=None,
    subject: str = "",
    text_body: str = "",
    html_body: str = "",
    in_reply_to: str = "",
    references: str = "",
    account=None,
):
    domain = from_email.split("@")[-1] if "@" in from_email else "mercury.local"
    msg = EmailMessage()
    msg["Message-ID"] = make_msgid(domain=domain)
    msg["Date"] = formatdate(localtime=True)
    msg["From"] = formataddr((from_name, from_email)) if from_email else "unknown@mercury.local"
    msg["To"] = _fmt(to)
    if cc:
        msg["Cc"] = _fmt(cc)
    if bcc:
        msg["Bcc"] = _fmt(bcc)
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(text_body or "")
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    # Stored copy keeps the Bcc header (own sent folder); the wire copy drops it.
    raw_for_store = msg.as_bytes()
    recipients = _emails(to) + _emails(cc) + _emails(bcc)

    cfg = _smtp_config(account)
    delivered, error = False, ""
    if cfg and recipients:
        # Don't leak Bcc on the wire (the stored copy above still has it).
        if msg["Bcc"]:
            del msg["Bcc"]
        try:
            srv = _connect_smtp(cfg)
            srv.send_message(msg, from_addr=from_email, to_addrs=recipients)
            srv.quit()
            delivered = True
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:400]
            logger.warning("smtp_send_failed", extra={"error": error})

    obj, _ = services.ingest_eml(owner, raw_for_store, source="compose", mailbox="sent")
    obj.is_read = True
    obj.metadata = {
        **(obj.metadata or {}),
        "delivered": delivered,
        "delivery_error": error,
        "relay_configured": bool(cfg),
    }
    obj.save(update_fields=["is_read", "metadata"])
    return obj, delivered, error
