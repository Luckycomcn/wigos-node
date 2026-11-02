import signal
import threading

from django.core.management.base import BaseCommand

from outbox import worker
from outbox.publishers import get_publishers


class Command(BaseCommand):
    help = "Publish queued station changes through settings.PUBLISHERS."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process the due events, then exit (tests, cron).")
        parser.add_argument("--workers", type=int, help="Threads (default settings.PUBLISHING_WORKERS).")

    def handle(self, *args, once=False, workers=None, **options):
        # docker stop sends SIGTERM: finish the current events, then exit
        stop = threading.Event()
        previous = signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())
        try:
            worker.run(get_publishers(), once=once, workers=workers, stop=stop)
        finally:
            signal.signal(signal.SIGTERM, previous)
