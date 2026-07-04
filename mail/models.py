"""Data model for the mercury email store.

One row per stored RFC822 message. The original bytes are preserved
(`raw_email`) so anything can be re-derived; normalized fields power
search/filter/threading. Adapted from the reference `stored_email` design with
per-user ownership (phoebe sub via authd) and a Postgres tsvector for search.
"""
import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone


class StoredEmail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Owner (phoebe sub) — every query is scoped to this. Dedup is per-owner.
    owner = models.CharField(max_length=128, db_index=True)

    # --- Identity / threading -------------------------------------------
    message_id = models.CharField(
        max_length=512, db_index=True, help_text="RFC Message-ID header."
    )
    in_reply_to = models.CharField(max_length=512, blank=True, default="", db_index=True)
    references = models.TextField(blank=True, default="")
    thread_key = models.CharField(
        max_length=512, blank=True, default="", db_index=True,
        help_text="App-level thread/grouping key.",
    )

    # --- Envelope / mailbox ---------------------------------------------
    delivered_to = models.EmailField(blank=True, default="", db_index=True)
    return_path = models.CharField(max_length=512, blank=True, default="", db_index=True)
    mailbox = models.CharField(max_length=255, blank=True, default="", db_index=True)
    source = models.CharField(
        max_length=64, blank=True, default="eml", db_index=True,
        help_text="Import source: eml, gmail, imap, ses, sendgrid, etc.",
    )

    # --- Core headers ---------------------------------------------------
    subject = models.TextField(blank=True, default="")
    from_name = models.CharField(max_length=255, blank=True, default="")
    from_email = models.EmailField(blank=True, default="", db_index=True)
    reply_to_name = models.CharField(max_length=255, blank=True, default="")
    reply_to_email = models.EmailField(blank=True, default="", db_index=True)
    sender_name = models.CharField(max_length=255, blank=True, default="")
    sender_email = models.EmailField(blank=True, default="", db_index=True)

    date_header = models.CharField(max_length=255, blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    received_at = models.DateTimeField(default=timezone.now, db_index=True)

    # --- Recipients (normalized JSON arrays) ----------------------------
    # [{"name": "...", "email": "..."}]
    to = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    bcc = models.JSONField(default=list, blank=True)

    # --- Body -----------------------------------------------------------
    text_body = models.TextField(blank=True, default="")
    html_body = models.TextField(blank=True, default="")
    body_preview = models.TextField(blank=True, default="")
    content_type = models.CharField(max_length=255, blank=True, default="")
    charset = models.CharField(max_length=64, blank=True, default="")
    is_multipart = models.BooleanField(default=False, db_index=True)

    # --- Mailing list / bulk metadata -----------------------------------
    list_id = models.CharField(max_length=512, blank=True, default="", db_index=True)
    list_unsubscribe = models.TextField(blank=True, default="")
    precedence = models.CharField(max_length=64, blank=True, default="", db_index=True)
    feedback_id = models.CharField(max_length=512, blank=True, default="")
    notification_type = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    provider_message_type = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )

    # --- Auth / security metadata ---------------------------------------
    spf_result = models.CharField(max_length=64, blank=True, default="", db_index=True)
    dkim_result = models.CharField(max_length=64, blank=True, default="", db_index=True)
    dmarc_result = models.CharField(max_length=64, blank=True, default="", db_index=True)
    authentication_results = models.TextField(blank=True, default="")
    received_spf = models.TextField(blank=True, default="")
    dkim_signature = models.TextField(blank=True, default="")

    # --- Raw preservation -----------------------------------------------
    headers = models.JSONField(default=dict, blank=True)
    raw_headers = models.TextField(blank=True, default="")
    raw_email = models.BinaryField(
        null=True, blank=True, help_text="Original RFC822 .eml bytes."
    )
    raw_size_bytes = models.PositiveIntegerField(default=0)

    # --- Attachments / flags --------------------------------------------
    has_attachments = models.BooleanField(default=False, db_index=True)
    attachment_count = models.PositiveIntegerField(default=0)
    # Lightweight attachment manifest (bytes stay in raw_email for now):
    # [{"filename": "...", "content_type": "...", "size": N, "content_id": "..."}]
    attachments = models.JSONField(default=list, blank=True)

    is_read = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    is_spam = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    labels = models.JSONField(default=list, blank=True)

    # --- Import / processing --------------------------------------------
    import_batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    parse_status = models.CharField(
        max_length=32, default="parsed", db_index=True,
        choices=[
            ("pending", "Pending"),
            ("parsed", "Parsed"),
            ("failed", "Failed"),
            ("partial", "Partial"),
        ],
    )
    parse_error = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Postgres full-text over subject / bodies / from — see mail.search.
    search_vector = SearchVectorField(null=True)

    class Meta:
        db_table = "stored_email"
        ordering = ["-sent_at", "-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "message_id"], name="uniq_owner_message_id"
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "-sent_at"], name="email_owner_sent"),
            models.Index(fields=["owner", "is_archived"], name="email_owner_arch"),
            models.Index(fields=["from_email", "sent_at"], name="email_from_sent"),
            models.Index(fields=["subject"], name="email_subject"),
            GinIndex(fields=["search_vector"], name="email_search_gin"),
        ]

    def __str__(self):
        return f"{self.subject[:80]} <{self.from_email}>"

    @property
    def best_body(self) -> str:
        return self.text_body or self.html_body or ""

    @property
    def primary_recipient_email(self) -> str:
        if self.to and isinstance(self.to, list):
            first = self.to[0]
            if isinstance(first, dict):
                return first.get("email", "")
        return ""
