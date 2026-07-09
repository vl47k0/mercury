"""Derive contacts from each owner's mail and push to the contacts service."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from mail.models import StoredEmail
from mail import contacts_sync


class Command(BaseCommand):
    help = "Build each user's address book from mail correspondents."

    def add_arguments(self, parser):
        parser.add_argument("--owner")

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
            res = contacts_sync.sync_owner(owner)
            total += res.get("pushed", 0)
            self.stdout.write(f"{owner[:16]}: {res}")
        self.stdout.write(self.style.SUCCESS(f"done — {total} contact(s) upserted"))
