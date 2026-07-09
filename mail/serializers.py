"""Serializers. raw_email (bytes) and search_vector are never serialized;
the raw .eml is downloaded via the dedicated /raw/ endpoint."""
from __future__ import annotations

from rest_framework import serializers

from .models import StoredEmail

_LIST_FIELDS = [
    "id", "message_id", "thread_key", "subject", "from_name", "from_email",
    "to", "sent_at", "received_at", "body_preview", "mailbox", "source",
    "list_id", "has_attachments", "attachment_count", "is_read", "is_archived",
    "is_spam", "labels", "spf_result", "dkim_result", "dmarc_result",
]


class EmailListSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoredEmail
        fields = _LIST_FIELDS


class EmailDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoredEmail
        exclude = ["raw_email", "search_vector"]


class EmailUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoredEmail
        fields = ["is_read", "is_archived", "is_spam", "is_deleted", "labels", "thread_key"]


from .models import MailAccount  # noqa: E402


class MailAccountSerializer(serializers.ModelSerializer):
    """Read view — never exposes the password; `has_password` flags whether one is set."""

    has_password = serializers.BooleanField(read_only=True)

    class Meta:
        model = MailAccount
        fields = [
            "id", "email", "display_name",
            "imap_host", "imap_port", "imap_ssl",
            "smtp_host", "smtp_port", "smtp_security",
            "username", "enabled", "folders",
            "has_password", "last_synced_at", "last_error",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "last_synced_at", "last_error", "created_at", "updated_at"]


class MailAccountWriteSerializer(serializers.ModelSerializer):
    """Upsert payload. `password` is write-only; omit it to keep the stored one."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = MailAccount
        fields = [
            "email", "display_name",
            "imap_host", "imap_port", "imap_ssl",
            "smtp_host", "smtp_port", "smtp_security",
            "username", "enabled", "folders", "password",
        ]
