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
