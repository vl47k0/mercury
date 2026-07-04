"""Parse raw RFC822 bytes into StoredEmail field values. Best-effort: a
malformed part never aborts the whole parse (fields just come back empty).
"""
from __future__ import annotations

import email
import hashlib
import re
from datetime import timezone as _tz
from email import policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime


def _addr_list(value: str) -> list[dict]:
    if not value:
        return []
    return [
        {"name": name, "email": addr}
        for (name, addr) in getaddresses([value])
        if addr
    ]


def _one_addr(value: str) -> tuple[str, str]:
    name, addr = parseaddr(value or "")
    return name, addr


def _auth_result(auth: str, method: str) -> str:
    m = re.search(rf"{method}=(\w+)", auth or "", re.IGNORECASE)
    return m.group(1).lower() if m else ""


def parse_eml(raw: bytes, owner: str, *, source: str = "eml", mailbox: str = "") -> dict:
    msg = email.message_from_bytes(raw, policy=policy.default)

    def h(name: str) -> str:
        v = msg.get(name)
        return str(v) if v is not None else ""

    from_name, from_email = _one_addr(h("From"))
    reply_name, reply_email = _one_addr(h("Reply-To"))
    sender_name, sender_email = _one_addr(h("Sender"))

    sent_at = None
    try:
        if msg.get("Date"):
            dt = parsedate_to_datetime(str(msg.get("Date")))
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)
            sent_at = dt
    except (TypeError, ValueError):
        pass

    # Bodies + attachment manifest.
    text_body, html_body = "", ""
    attachments: list[dict] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()
        if "attachment" in disp.lower() or filename:
            try:
                payload = part.get_payload(decode=True) or b""
            except Exception:
                payload = b""
            attachments.append(
                {
                    "filename": filename or "",
                    "content_type": ctype,
                    "size": len(payload),
                    "content_id": (part.get("Content-ID") or "").strip("<>"),
                }
            )
            continue
        try:
            if ctype == "text/plain" and not text_body:
                text_body = part.get_content()
            elif ctype == "text/html" and not html_body:
                html_body = part.get_content()
        except Exception:
            pass

    # Preview from text, else stripped HTML.
    preview_src = text_body or re.sub(r"<[^>]+>", " ", html_body or "")
    body_preview = re.sub(r"\s+", " ", preview_src).strip()[:280]

    # All headers, repeated headers kept as lists.
    headers: dict[str, list[str]] = {}
    for k, v in msg.items():
        headers.setdefault(k, []).append(str(v))

    raw_headers = re.split(rb"\r?\n\r?\n", raw, 1)[0].decode("utf-8", "replace")
    auth = h("Authentication-Results")

    message_id = h("Message-ID") or h("Message-Id")
    if not message_id:
        message_id = f"<{hashlib.sha256(raw).hexdigest()}@mercury.local>"

    return {
        "owner": owner,
        "source": source,
        "mailbox": mailbox,
        "message_id": message_id.strip(),
        "in_reply_to": h("In-Reply-To").strip(),
        "references": h("References"),
        "delivered_to": _one_addr(h("Delivered-To"))[1],
        "return_path": h("Return-Path").strip("<> "),
        "subject": h("Subject"),
        "from_name": from_name,
        "from_email": from_email,
        "reply_to_name": reply_name,
        "reply_to_email": reply_email,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "date_header": h("Date"),
        "sent_at": sent_at,
        "to": _addr_list(h("To")),
        "cc": _addr_list(h("Cc")),
        "bcc": _addr_list(h("Bcc")),
        "text_body": text_body or "",
        "html_body": html_body or "",
        "body_preview": body_preview,
        "content_type": msg.get_content_type(),
        "charset": msg.get_content_charset() or "",
        "is_multipart": msg.is_multipart(),
        "list_id": h("List-Id"),
        "list_unsubscribe": h("List-Unsubscribe"),
        "precedence": h("Precedence"),
        "feedback_id": h("Feedback-ID"),
        "spf_result": _auth_result(auth, "spf"),
        "dkim_result": _auth_result(auth, "dkim"),
        "dmarc_result": _auth_result(auth, "dmarc"),
        "authentication_results": auth,
        "received_spf": h("Received-SPF"),
        "dkim_signature": h("DKIM-Signature"),
        "headers": headers,
        "raw_headers": raw_headers,
        "raw_email": raw,
        "raw_size_bytes": len(raw),
        "has_attachments": bool(attachments),
        "attachment_count": len(attachments),
        "attachments": attachments,
    }
