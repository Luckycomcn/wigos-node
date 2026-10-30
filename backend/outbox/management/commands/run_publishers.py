from django.core.management.base import BaseCommand

from outbox import worker
from outbox.publishers import get_publishers


class Command(BaseCommand):
    help = "Publish queued station changes through settings.PUBLISHERS."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process the due events, then exit (tests, cron).")

    def handle(self, *args, once=False, **options):
        worker.run(get_publishers(), once=once)
