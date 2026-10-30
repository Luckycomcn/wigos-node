"""Run queued PublicationEvents through the configured publishers.

The worker sleeps until a committed change NOTIFYs it (see signals.py), with
a poll every POLL_INTERVAL as a fallback.

Events are processed in parallel threads (settings.PUBLISHING_WORKERS),
oldest first. An event waits while an older event that still holds its
resources shares one of its ordering keys (same station, or a WIGOS
identifier it had or has), so a station's changes are published in order.
A failed event stays in the log but releases its keys once it is cleaned up
(everything undone); one whose undo failed keeps holding them.

Publishers run in order for each event, and each one gets the receipts of
the ones before it. After every publisher the row records it in `completed`
with its receipts, so a retry skips it and reuses what it stored. When an
event runs out of attempts it becomes `failed` and its completed publishers
are undone, newest first.

A claimed event is `processing` with a lease (`locked_until`), renewed after
every publisher. A worker that dies leaves the lease to expire; the event
is then claimed again and the crash counts as a failed attempt. A single
publisher must therefore finish within LEASE. Every time the worker sets or
compares comes from the database clock, so workers on hosts whose clocks
differ still agree on when a lease expires."""

import logging
import select
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.db.models import Exists, OuterRef, Q

from publishing.base import Delivery, Location, Message, Operation, PublishError

from .models import PublicationEvent

logger = logging.getLogger("outbox")

MAX_ATTEMPTS = 5
RETRY_DELAY = timedelta(seconds=30)  # doubled after every failed attempt
MAX_RETRY_DELAY = timedelta(hours=1)
LEASE = timedelta(minutes=5)
POLL_INTERVAL = 30  # seconds between looks at the queue without a notification
RECONNECT_DELAY = 5  # seconds before listening again after a lost connection
CHANNEL = "publishing"  # NOTIFY channel; the payload is the event id

Status = PublicationEvent.Status
FINISHED = [Status.PROCESSED, Status.PUBLISHED]
# events that no longer hold back the events after them
RELEASED = Q(status__in=FINISHED) | Q(status=Status.FAILED, completed__len=0)


class LeaseLost(Exception):
    """Another worker took the event over after this one's lease expired."""


def dump_delivery(delivery):
    """A receipt as saved on the row. The body isn't kept: a later
    publisher that needs the file retrieves it from its location."""
    location = delivery.location
    return {
        "publisher": delivery.publisher,
        "name": delivery.message.name,
        "media_type": delivery.message.media_type,
        "topic": delivery.message.topic,
        "url": location.url if location else None,
        "internal_url": location.internal_url if location else None,
    }


def load_delivery(data):
    return Delivery(
        publisher=data["publisher"],
        message=Message(body=b"", media_type=data["media_type"], name=data["name"], topic=data["topic"]),
        location=Location(data["url"], data["internal_url"]) if data["url"] else None,
    )


def db_now():
    """The database's current time (clock_timestamp(), not now(): that is
    the start of the transaction)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT clock_timestamp()")
        return cursor.fetchone()[0]


def retry_delay(attempts):
    return min(RETRY_DELAY * 2 ** (attempts - 1), MAX_RETRY_DELAY)


def claim():
    """Take the oldest claimable event: pending and due, or processing with
    an expired lease (its worker crashed, which counts as a failed attempt).
    Events behind an older unreleased event sharing an ordering key are
    skipped. Returns the event, now processing under a new lease, or None."""
    now = db_now()
    blocking = PublicationEvent.objects.filter(
        id__lt=OuterRef("id"),
        ordering_keys__overlap=OuterRef("ordering_keys"),
    ).exclude(RELEASED)
    due = Q(status=Status.PENDING) & (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
    crashed = Q(status=Status.PROCESSING, locked_until__lt=now)
    with transaction.atomic():
        row = (
            PublicationEvent.objects.select_for_update(skip_locked=True)
            .filter(due | crashed)
            .exclude(Exists(blocking))
            .order_by("id")
            .first()
        )
        if row is None:
            return None
        if row.status == Status.PROCESSING:
            row.attempts += 1
            row.last_error = f"worker stopped while processing (lease expired at {row.locked_until})"
            logger.warning("Event %s: %s", row.id, row.last_error)
        row.status = Status.PROCESSING
        row.locked_until = now + LEASE
        row.save(update_fields=["status", "locked_until", "attempts", "last_error"])
    return row


def save(row, *fields):
    """Save fields while this worker still holds the lease, renewing it while
    the event stays processing (and dropping it otherwise)."""
    lease = db_now() + LEASE if row.status == Status.PROCESSING else None
    updated = PublicationEvent.objects.filter(
        pk=row.pk, status=Status.PROCESSING, locked_until=row.locked_until
    ).update(locked_until=lease, **{field: getattr(row, field) for field in fields})
    if not updated:
        raise LeaseLost(row.pk)
    row.locked_until = lease


def earlier_deliveries(row):
    """What a DELETE refers to: the receipts of the station's last finished
    event (the deletion WNM links to that file). Nothing for other events.
    These belong to that event, so they are never saved here or undone."""
    if row.operation != Operation.DELETE:
        return []
    last = (
        PublicationEvent.objects.filter(station_id=row.station_id, status__in=FINISHED, id__lt=row.id)
        .order_by("-id")
        .first()
    )
    return [load_delivery(d) for d in last.deliveries] if last else []


def process(row, publishers):
    """Run one claimed event through the publishers and record the outcome."""
    event = row.to_event()
    earlier = earlier_deliveries(row)
    own = [load_delivery(d) for d in row.deliveries]
    if row.attempts >= MAX_ATTEMPTS:  # the last attempt crashed
        give_up(row, publishers, event, own)
        return
    for publisher in publishers:
        if publisher.name in row.completed:
            continue
        try:
            delivered = publisher.publish(event, earlier + own)
        except Exception as e:
            if not isinstance(e, PublishError):  # a bug, not an outage
                logger.exception("Publisher %s crashed on event %s", publisher.name, row.id)
            fail_attempt(row, publishers, event, own, f"{publisher.name}: {e}")
            return
        own += delivered
        row.completed.append(publisher.name)
        row.deliveries = [dump_delivery(d) for d in own]
        save(row, "completed", "deliveries")

    row.status = Status.PROCESSED
    row.finished_at = db_now()
    row.next_attempt_at = None
    save(row, "status", "finished_at", "next_attempt_at")
    logger.info("Processed event %s (%s %s)", row.id, row.operation, row.wigos_identifier)


def fail_attempt(row, publishers, event, own, error):
    row.attempts += 1
    row.last_error = error
    if row.attempts >= MAX_ATTEMPTS:
        give_up(row, publishers, event, own)
        return
    row.status = Status.PENDING
    row.next_attempt_at = db_now() + retry_delay(row.attempts)
    logger.warning("Event %s failed (attempt %d), retrying at %s: %s", row.id, row.attempts, row.next_attempt_at, error)
    save(row, "status", "attempts", "last_error", "next_attempt_at")


def give_up(row, publishers, event, own):
    row.status = Status.FAILED
    row.finished_at = db_now()
    row.next_attempt_at = None
    logger.error("Event %s failed after %d attempts, undoing: %s", row.id, row.attempts, row.last_error)
    undo(row, publishers, event, own)
    save(row, "status", "attempts", "last_error", "next_attempt_at", "finished_at", "completed", "deliveries")


def undo(row, publishers, event, own):
    """Undo the completed publishers, newest first. One that undid cleanly
    leaves `completed` together with its receipts; one that couldn't stays,
    so the row shows what may still be stored."""
    for publisher in reversed(publishers):
        if publisher.name not in row.completed:
            continue
        try:
            publisher.undo(event, own)
        except Exception as e:
            logger.exception("Could not undo %s for event %s", publisher.name, row.id)
            row.last_error += f"\nundo {publisher.name}: {e}"
            continue
        row.completed.remove(publisher.name)
        own = [d for d in own if d.publisher != publisher.name]
    row.deliveries = [dump_delivery(d) for d in own]


def process_next(publishers):
    """Claim and process one event; False when nothing is claimable."""
    row = claim()
    if row is None:
        return False
    try:
        process(row, publishers)
    except LeaseLost:
        logger.warning("Event %s was taken over by another worker after its lease expired", row.id)
    return True


def notify(event_id):
    """Wake the listening workers. Called through transaction.on_commit, so
    a change that is rolled back wakes nobody."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_notify(%s, %s)", [CHANNEL, str(event_id)])


class Wakeup:
    """Lets idle threads sleep until there may be new work. The generation
    counter keeps a wake-up that comes between a thread's look at the queue
    and its wait from being missed."""

    def __init__(self):
        self._condition = threading.Condition()
        self._generation = 0

    def current(self):
        with self._condition:
            return self._generation

    def wake(self):
        with self._condition:
            self._generation += 1
            self._condition.notify_all()

    def wait(self, seen, timeout=None):
        """Wait until woken after generation `seen`; False on timeout."""
        with self._condition:
            return self._condition.wait_for(lambda: self._generation != seen, timeout)


def listen(wakeup, stop, ready=None):
    """LISTEN on CHANNEL and wake the threads for every notification, and
    every POLL_INTERVAL anyway: retries that became due, expired leases and
    notifications missed while disconnected send none. Returns once `stop`
    is set (checked every second); `ready` is set once listening."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"LISTEN {CHANNEL}")
        pg = connection.connection
        if ready:
            ready.set()
        polled = time.monotonic()
        while not stop.is_set():
            if select.select([pg], [], [], 1)[0]:
                pg.poll()
                if pg.notifies:
                    pg.notifies.clear()
                    wakeup.wake()
                    polled = time.monotonic()
                    continue
            if time.monotonic() - polled >= POLL_INTERVAL:
                wakeup.wake()
                polled = time.monotonic()
    finally:
        connection.close()  # also ends the LISTEN


def keep_listening(wakeup, stop, ready=None):
    """listen(), reconnecting after a lost connection."""
    while not stop.is_set():
        try:
            listen(wakeup, stop, ready)
        except (DatabaseError, OSError):
            logger.exception("Lost the notification connection, reconnecting in %d s", RECONNECT_DELAY)
            wakeup.wake()  # look at the queue in case notifications were missed
            stop.wait(RECONNECT_DELAY)


def work(publishers, once, wakeup, stop):
    """One thread: process events until none is claimable (once), or until
    `stop`, sleeping while idle until woken."""
    try:
        while not stop.is_set():
            seen = wakeup.current()
            try:
                if process_next(publishers):
                    close_old_connections()
                    continue
            except Exception:
                if once:
                    raise
                logger.exception("Worker thread error, continuing at the next wake-up")
            if once:
                return
            wakeup.wait(seen)
    finally:
        connection.close()  # this thread's own connection


def run(publishers, once=False, workers=None, stop=None, ready=None):
    """Process events in `workers` threads (default settings.PUBLISHING_WORKERS)
    sharing the publishers, whose transports are opened once. Without `once`
    this runs until `stop` is set; the threads finish their current event
    first."""
    workers = workers or settings.PUBLISHING_WORKERS
    stop = stop or threading.Event()
    wakeup = Wakeup()
    for publisher in publishers:
        publisher.open()
    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="publisher") as pool:
            futures = [pool.submit(work, publishers, once, wakeup, stop) for _ in range(workers)]
            if not once:
                try:
                    keep_listening(wakeup, stop, ready)
                finally:
                    stop.set()
                    wakeup.wake()
            for future in futures:
                future.result()
    finally:
        for publisher in publishers:
            publisher.close()
