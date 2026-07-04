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

    delivered, error = False, ""
    if settings.SMTP_HOST and recipients:
        # Don't leak Bcc on the wire (the stored copy above still has it).
        if msg["Bcc"]:
            del msg["Bcc"]
        try:
            if settings.SMTP_SSL:
                srv = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            else:
                srv = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
                if settings.SMTP_TLS:
                    srv.starttls()
            if settings.SMTP_USER:
                srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
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
        "relay_configured": bool(settings.SMTP_HOST),
    }
    obj.save(update_fields=["is_read", "metadata"])
    return obj, delivered, error
