"""Push each owner's stored mail into the orion RAG corpus (run via CronJob)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from mail.models import StoredEmail
from mail import orion_sync


class Command(BaseCommand):
    help = "Sync stored mail into orion's per-user RAG corpus."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Only sync this owner.")
        parser.add_argument("--limit", type=int, help="Cap messages per owner.")

    def handle(self, *args, **opts):
        if opts.get("owner"):
            owners = [opts["owner"]]
        else:
            owners = list(
                StoredEmail.objects.filter(is_deleted=False)
                .values_list("owner", flat=True).distinct()
            )
        total = 0
        for owner in owners:
            res = orion_sync.sync_owner(owner, limit=opts.get("limit"))
            total += res.get("pushed", 0)
            self.stdout.write(f"{owner[:16]}: {res}")
        self.stdout.write(self.style.SUCCESS(f"done — {total} message(s) (re)ingested"))
