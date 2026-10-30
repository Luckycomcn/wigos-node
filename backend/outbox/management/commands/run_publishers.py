from django.core.management.base import BaseCommand

from outbox import worker
from outbox.publishers import get_publishers


class Command(BaseCommand):
    help = "Publish queued station changes through settings.PUBLISHERS."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process the due events, then exit (tests, cron).")
        parser.add_argument("--workers", type=int, help="Threads (default settings.PUBLISHING_WORKERS).")

    def handle(self, *args, once=False, workers=None, **options):
        worker.run(get_publishers(), once=once, workers=workers)
