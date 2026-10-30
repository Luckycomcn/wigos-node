"""Run queued PublicationEvents through the configured publishers.

One event at a time, oldest first. An event waits while an older event that
still holds its resources shares one of its ordering keys (same station, or
a WIGOS identifier it had or has), so a station's changes are published in
order. A failed event stays in the log but releases its keys once it is
cleaned up (everything undone); one whose undo failed keeps holding them.

Publishers run in order for each event, and each one gets the receipts of
the ones before it. After every publisher the row records it in `completed`
with its receipts, so a retry skips it and reuses what it stored. When an
event runs out of attempts it becomes `failed` and its completed publishers
are undone, newest first.

For now the row lock is held while the event is processed; a crash rolls
the transaction back and the event is simply pending again."""

import logging
import time
from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from publishing.base import Delivery, Location, Message, Operation, PublishError

from .models import PublicationEvent

logger = logging.getLogger("outbox")

MAX_ATTEMPTS = 5
RETRY_DELAY = timedelta(seconds=30)  # doubled after every failed attempt
MAX_RETRY_DELAY = timedelta(hours=1)
POLL_INTERVAL = 30  # seconds between looks at the queue when it is empty

FINISHED = [PublicationEvent.Status.PROCESSED, PublicationEvent.Status.PUBLISHED]
# events that no longer hold back the events after them
RELEASED = Q(status__in=FINISHED) | Q(status=PublicationEvent.Status.FAILED, completed__len=0)


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


def retry_delay(attempts):
    return min(RETRY_DELAY * 2 ** (attempts - 1), MAX_RETRY_DELAY)


def claim():
    """The oldest due pending event with no older unreleased event sharing an
    ordering key, locked for this transaction; None if there is none."""
    blocking = PublicationEvent.objects.filter(
        id__lt=OuterRef("id"),
        ordering_keys__overlap=OuterRef("ordering_keys"),
    ).exclude(RELEASED)
    return (
        PublicationEvent.objects.select_for_update(skip_locked=True)
        .filter(status=PublicationEvent.Status.PENDING)
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()))
        .exclude(Exists(blocking))
        .order_by("id")
        .first()
    )


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
    for publisher in publishers:
        if publisher.name in row.completed:
            continue
        try:
            delivered = publisher.publish(event, earlier + own)
        except Exception as e:
            if not isinstance(e, PublishError):  # a bug, not an outage
                logger.exception("Publisher %s crashed on event %s", publisher.name, row.id)
            give_up_or_retry(row, publishers, event, own, f"{publisher.name}: {e}")
            return
        own += delivered
        row.completed.append(publisher.name)
        row.deliveries = [dump_delivery(d) for d in own]
        row.save(update_fields=["completed", "deliveries"])

    row.status = PublicationEvent.Status.PROCESSED
    row.finished_at = timezone.now()
    row.next_attempt_at = None
    row.save(update_fields=["status", "finished_at", "next_attempt_at"])
    logger.info("Processed event %s (%s %s)", row.id, row.operation, row.wigos_identifier)


def give_up_or_retry(row, publishers, event, own, error):
    row.attempts += 1
    row.last_error = error
    if row.attempts < MAX_ATTEMPTS:
        row.next_attempt_at = timezone.now() + retry_delay(row.attempts)
        logger.warning("Event %s failed (attempt %d), retrying at %s: %s", row.id, row.attempts, row.next_attempt_at, error)
    else:
        row.status = PublicationEvent.Status.FAILED
        row.finished_at = timezone.now()
        row.next_attempt_at = None
        logger.error("Event %s failed after %d attempts, undoing: %s", row.id, row.attempts, error)
        undo(row, publishers, event, own)
    row.save(update_fields=["attempts", "last_error", "next_attempt_at", "status", "finished_at", "completed", "deliveries"])


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
    """Claim and process one event; False when nothing is due."""
    with transaction.atomic():
        row = claim()
        if row is None:
            return False
        process(row, publishers)
    return True


def run(publishers, once=False):
    """Process events until none is due (once), or forever."""
    for publisher in publishers:
        publisher.open()
    try:
        while True:
            while process_next(publishers):
                pass
            if once:
                return
            time.sleep(POLL_INTERVAL)
    finally:
        for publisher in publishers:
            publisher.close()
