"""Mailbox API — all scoped to the authenticated owner (phoebe sub via authd).

  GET/POST  /api/v1/messages/            list (filter/search) / import .eml
  GET/PATCH/DELETE /api/v1/messages/<id>/  detail / flags+labels / delete
  GET       /api/v1/messages/<id>/raw/   download the original .eml
  GET       /api/v1/stats/               mailbox totals
"""
from __future__ import annotations

import logging
import uuid

from django.contrib.postgres.search import SearchRank
from django.http import Http404, HttpResponse
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from . import search, sender, services
from .models import StoredEmail
from .serializers import (
    EmailDetailSerializer,
    EmailListSerializer,
    EmailUpdateSerializer,
)

logger = logging.getLogger(__name__)


class _OwnerMixin:
    def owner(self) -> str:
        return self.request.user.id

    def base_qs(self):
        return StoredEmail.objects.filter(owner=self.owner())


class MessageListView(_OwnerMixin, generics.ListCreateAPIView):
    serializer_class = EmailListSerializer

    def get_queryset(self):
        qs = search.apply_filters(self.base_qs(), self.request.query_params)
        sq = search.text_query(self.request.query_params)
        if sq is not None:
            return qs.annotate(rank=SearchRank("search_vector", sq)).order_by(
                "-rank", "-sort_ts"
            )
        return qs.order_by("-sort_ts")

    def create(self, request, *args, **kwargs):
        """Import one or more raw .eml files (multipart `files`)."""
        files = request.FILES.getlist("files")
        if not files and "file" in request.FILES:
            files = [request.FILES["file"]]
        if not files:
            return Response({"detail": "No .eml file(s) provided."}, status=400)

        source = request.data.get("source", "eml")
        mailbox = request.data.get("mailbox", "")
        batch_id = uuid.uuid4()
        imported, duplicates, errors = [], 0, []
        for f in files:
            try:
                obj, created = services.ingest_eml(
                    self.owner(),
                    f.read(),
                    source=source,
                    mailbox=mailbox,
                    batch_id=batch_id,
                )
                if created:
                    imported.append(obj)
                else:
                    duplicates += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("import_failed", extra={"filename": f.name})
                errors.append({"filename": f.name, "error": str(exc)})
        return Response(
            {
                "batch_id": str(batch_id),
                "imported": EmailListSerializer(imported, many=True).data,
                "imported_count": len(imported),
                "duplicates": duplicates,
                "errors": errors,
            },
            status=201 if imported else 200,
        )


class MessageDetailView(_OwnerMixin, generics.RetrieveUpdateDestroyAPIView):
    def get_queryset(self):
        return self.base_qs()

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return EmailUpdateSerializer
        return EmailDetailSerializer


class RawMessageView(_OwnerMixin, APIView):
    def get(self, request, pk):
        try:
            msg = self.base_qs().get(pk=pk)
        except StoredEmail.DoesNotExist:
            raise Http404
        if not msg.raw_email:
            raise Http404
        resp = HttpResponse(bytes(msg.raw_email), content_type="message/rfc822")
        resp["Content-Disposition"] = f'attachment; filename="{pk}.eml"'
        return resp


class SendView(_OwnerMixin, APIView):
    """Compose + send. Body: {to, cc?, bcc?, subject, text_body, html_body?,
    in_reply_to?, references?}. Addresses are strings or {name,email}."""

    def post(self, request):
        d = request.data
        to = d.get("to") or []
        if not to:
            return Response({"detail": "At least one recipient is required."}, status=400)
        from_email = getattr(request.user, "email", "") or settings.SMTP_DEFAULT_FROM
        obj, delivered, error = sender.send_message(
            self.owner(),
            from_email=from_email,
            from_name=d.get("from_name", ""),
            to=to,
            cc=d.get("cc"),
            bcc=d.get("bcc"),
            subject=d.get("subject", ""),
            text_body=d.get("text_body", ""),
            html_body=d.get("html_body", ""),
            in_reply_to=d.get("in_reply_to", ""),
            references=d.get("references", ""),
        )
        return Response(
            {
                "message": EmailDetailSerializer(obj).data,
                "delivered": delivered,
                "error": error,
                "relay_configured": bool(settings.SMTP_HOST),
            },
            status=201,
        )


class StatsView(_OwnerMixin, APIView):
    def get(self, request):
        qs = self.base_qs().filter(is_deleted=False)
        return Response(
            {
                "total": qs.count(),
                "unread": qs.filter(is_read=False).count(),
                "archived": qs.filter(is_archived=True).count(),
                "with_attachments": qs.filter(has_attachments=True).count(),
            }
        )
