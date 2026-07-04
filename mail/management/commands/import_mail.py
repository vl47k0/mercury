"""Bulk-import email into an owner's mailbox.

    python manage.py import_mail <owner> <path> [<path> ...] [--recursive]

Paths may be .eml files, directories of .eml files, or .mbox files.
"""
from __future__ import annotations

import mailbox
from pathlib import Path

from django.core.management.base import BaseCommand

from mail import services


class Command(BaseCommand):
    help = "Import .eml / .mbox email into an owner's mailbox."

    def add_arguments(self, parser):
        parser.add_argument("owner")
        parser.add_argument("paths", nargs="+")
        parser.add_argument("--recursive", action="store_true")
        parser.add_argument("--mailbox", default="")

    def handle(self, *args, **opts):
        owner, mbx = opts["owner"], opts["mailbox"]
        imported = dup = fail = 0

        def ingest(raw, source):
            nonlocal imported, dup, fail
            try:
                _, created = services.ingest_eml(owner, raw, source=source, mailbox=mbx)
                imported += 1 if created else 0
                dup += 0 if created else 1
            except Exception as exc:  # noqa: BLE001
                fail += 1
                self.stderr.write(f"ERROR: {exc}")

        for p in opts["paths"]:
            path = Path(p)
            if path.suffix.lower() == ".mbox" or (path.is_file() and path.suffix.lower() == ".mbox"):
                for m in mailbox.mbox(str(path)):
                    ingest(m.as_bytes(), "mbox")
            elif path.is_dir():
                g = path.rglob("*.eml") if opts["recursive"] else path.glob("*.eml")
                for f in g:
                    ingest(f.read_bytes(), "eml")
            elif path.is_file():
                ingest(path.read_bytes(), "eml")

        self.stdout.write(
            self.style.SUCCESS(f"imported={imported} duplicates={dup} failed={fail}")
        )
