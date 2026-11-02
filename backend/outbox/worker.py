"""Run queued PublicationEvents through the configured publishers.

The worker sleeps until a committed change NOTIFYs it (see signals.py), with
a poll every POLL_INTERVAL as a fallback.

Events are processed in parallel threads (settings.PUBLISHING_WORKERS),
oldest first. An event waits while an older event that still holds its
resources shares one of its ordering keys (same station, or a WIGOS
identifier it had or has), so a station's changes are published in order.
A failed event stays in the log but releases its keys, unless its undo failed
(`needs_cleanup`): that one keeps holding them.

Each publisher is one process from start to end, and they don't affect each
other. After every step of a publisher the row records it in `completed` with
its receipts. When an event runs out of attempts (see MAX_ATTEMPTS) it becomes
`failed` and the publishers that failed are undone.

A claimed event is `processing` with a lease (`locked_until`), renewed after
every step. A worker that dies leaves the lease to expire; the event
is then claimed again and resumes after its completed publishers. A single
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

from publishing.base import Delivery, Location, Message, PublishError

from .models import PublicationEvent

logger = logging.getLogger("outbox")

# Retries are manual: the first failure makes the event failed, and a user
# retries it. Raising this turns on automatic retries with backoff.
MAX_ATTEMPTS = 1
RETRY_DELAY = timedelta(seconds=30)  # doubled after every failed attempt
MAX_RETRY_DELAY = timedelta(hours=1)
LEASE = timedelta(minutes=5)
POLL_INTERVAL = 30  # seconds between looks at the queue without a notification
RECONNECT_DELAY = 5  # seconds before listening again after a lost connection
CHANNEL = "publishing"  # NOTIFY channel; the payload is the event id

Status = PublicationEvent.Status
FINISHED = [Status.PROCESSED, Status.PUBLISHED]
# events that no longer hold back the events after them
RELEASED = Q(status__in=FINISHED) | Q(status=Status.FAILED, needs_cleanup=False)


class LeaseLost(Exception):
    """Another worker took the event over after this one's lease expired."""


def dump_delivery(delivery):
    """A receipt as saved on the row. The body isn't kept: a later
    publisher that needs the file retrieves it from its location."""
    location = delivery.location
    return {
        "publisher": delivery.publisher,
        "step": delivery.step,
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
        step=data.get("step"),
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
    an expired lease (its worker crashed, so it resumes). Events behind an
    older unreleased event sharing an ordering key are skipped. Returns the event, now processing under a new lease, or None."""
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
            row.last_error = f"worker stopped while processing (lease expired at {row.locked_until})"
            logger.warning("Event %s: %s", row.id, row.last_error)
        row.status = Status.PROCESSING
        row.locked_until = now + LEASE
        row.save(update_fields=["status", "locked_until", "last_error"])
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


def receipts_of(row, publisher):
    return [load_delivery(d) for d in row.deliveries if d["publisher"] == publisher.name]


def previous_deliveries(row, publisher):
    """This publisher's receipts from the station's last change it delivered
    (a deletion WNM links to that file). They belong to that event, so they
    are never saved here or undone."""
    last = (
        PublicationEvent.objects.filter(
            station_id=row.station_id,
            id__lt=row.id,
            deliveries__contains=[{"publisher": publisher.name}],
            needs_cleanup=False,
        )
        .order_by("-id")
        .first()
    )
    return receipts_of(last, publisher) if last else []


def step_key(publisher, step_name):
    """How a publisher's step is recorded in `completed`."""
    return f"{publisher.name}:{step_name}"


def run_publisher(row, publisher, event):
    """Run one publisher, saving its progress after every step."""
    prefix = step_key(publisher, "")

    def record(step, receipts):
        row.completed.append(step_key(publisher, step.name))
        others = [d for d in row.deliveries if d["publisher"] != publisher.name]
        row.deliveries = others + [dump_delivery(d) for d in receipts]
        save(row, "completed", "deliveries")

    publisher.publish(
        event,
        receipts_of(row, publisher),
        done=[key.removeprefix(prefix) for key in row.completed if key.startswith(prefix)],
        previous=previous_deliveries(row, publisher),
        on_step=record,
    )


def describe_failure(row, publisher, error):
    """`error`, prefixed with the publisher and the step that didn't finish."""
    pending = (s.name for s in publisher.steps if step_key(publisher, s.name) not in row.completed)
    return f"{step_key(publisher, next(pending, '?'))}: {error}"


def process(row, publishers):
    """Run one claimed event through the publishers and record the outcome.
    Publishers are independent: one failing doesn't stop or undo the others."""
    event = row.to_event()
    failures = []
    for publisher in publishers:
        try:
            run_publisher(row, publisher, event)
        except LeaseLost:
            raise
        except Exception as e:
            if not isinstance(e, PublishError):  # a bug, not an outage
                logger.exception("Publisher %s crashed on event %s", publisher.name, row.id)
            failures.append((publisher, describe_failure(row, publisher, e)))
    if failures:
        fail_attempt(row, event, failures)
        return

    row.status = Status.PROCESSED
    row.finished_at = db_now()
    row.next_attempt_at = None
    save(row, "status", "finished_at", "next_attempt_at")
    logger.info("Processed event %s (%s %s)", row.id, row.operation, row.wigos_identifier)


def fail_attempt(row, event, failures):
    row.attempts += 1
    row.last_error = "\n".join(error for _, error in failures)
    if row.attempts >= MAX_ATTEMPTS:
        give_up(row, event, [publisher for publisher, _ in failures])
        return
    row.status = Status.PENDING
    row.next_attempt_at = db_now() + retry_delay(row.attempts)
    logger.warning(
        "Event %s failed (attempt %d), retrying at %s: %s", row.id, row.attempts, row.next_attempt_at, row.last_error
    )
    save(row, "status", "attempts", "last_error", "next_attempt_at")


def give_up(row, event, publishers):
    """Mark the event failed and undo the publishers that failed; the others
    delivered their part, which stays."""
    row.status = Status.FAILED
    row.finished_at = db_now()
    row.next_attempt_at = None
    logger.error("Event %s failed after %d attempts, undoing: %s", row.id, row.attempts, row.last_error)
    for publisher in publishers:
        undo(row, publisher, event)
    save(
        row,
        "status", "attempts", "last_error", "next_attempt_at", "finished_at",
        "completed", "deliveries", "needs_cleanup",
    )


def undo(row, publisher, event):
    """Undo a publisher's completed steps. If that works its steps leave
    `completed` together with their receipts. If not they stay, so the row
    shows what may still be stored, and it needs cleaning up."""
    try:
        publisher.undo(event, receipts_of(row, publisher))
    except Exception as e:
        logger.exception("Could not undo %s for event %s", publisher.name, row.id)
        row.last_error += f"\nundo {publisher.name}: {e}"
        row.needs_cleanup = True
        return
    prefix = step_key(publisher, "")
    row.completed = [key for key in row.completed if not key.startswith(prefix)]
    row.deliveries = [d for d in row.deliveries if d["publisher"] != publisher.name]


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
