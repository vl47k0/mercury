"""Fetch new inbound mail for every enabled MailAccount (run via CronJob)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from mail import imap_client
from mail.models import MailAccount


class Command(BaseCommand):
    help = "Poll IMAP inbound for all enabled mail accounts."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Only poll this owner's account.")

    def handle(self, *args, **opts):
        qs = MailAccount.objects.filter(enabled=True)
        if opts.get("owner"):
            qs = qs.filter(owner=opts["owner"])
        total_new = 0
        for account in qs:
            res = imap_client.fetch_new(account)
            total_new += res.get("new", 0)
            self.stdout.write(
                f"{account.email}: ok={res.get('ok')} fetched={res.get('fetched')} "
                f"new={res.get('new')} {res.get('error','')}"
            )
        self.stdout.write(self.style.SUCCESS(f"done — {total_new} new message(s)"))
