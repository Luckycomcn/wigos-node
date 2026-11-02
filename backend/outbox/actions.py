"""What an admin can do about a failed event. Retries are manual, so this is the
way a failed event gets published after all."""

from functools import partial

from django.db import transaction

from . import worker
from .models import PublicationEvent

Status = PublicationEvent.Status


class ActionRefused(Exception):
    """The action can't be done on this event; the message says why."""


def _complete_publishers(row, publishers):
    failed = worker.failed_publishers(row, publishers)
    return [p for p in publishers if p not in failed]


def leftovers(row, publishers):
    """The receipts of publishers that didn't finish, including publishers no
    longer configured: what may still be stored."""
    complete = {p.name for p in _complete_publishers(row, publishers)}
    return [d for d in row.deliveries if d["publisher"] not in complete]


def _forget_leftovers(row, publishers):
    complete = _complete_publishers(row, publishers)
    prefixes = tuple(worker.step_key(p, "") for p in complete)
    names = {p.name for p in complete}
    row.completed = [key for key in row.completed if key.startswith(prefixes)]
    row.deliveries = [d for d in row.deliveries if d["publisher"] in names]


def retry(pk, publishers):
    """Queue a failed event again. The publishers that failed run all their
    steps, so the file is regenerated from the event's snapshot and the
    integrity computed from it as served; those that succeeded don't send
    again. An old version must not be announced after a newer one, so this is
    refused once a later event shares an ordering key."""
    with transaction.atomic():
        row = PublicationEvent.objects.select_for_update().get(pk=pk)
        if row.status != Status.FAILED:
            raise ActionRefused(f"it is {row.status}, and only failed events can be retried")
        later = PublicationEvent.objects.filter(id__gt=row.id, ordering_keys__overlap=row.ordering_keys)
        if later.exists():
            raise ActionRefused("a later change touches the same station or WIGOS IDs; save the station again instead")
        _forget_leftovers(row, publishers)
        row.status = Status.PENDING
        row.attempts = 0
        row.next_attempt_at = None
        row.finished_at = None
        row.needs_cleanup = False
        row.save(update_fields=[
            "status", "attempts", "next_attempt_at", "finished_at", "needs_cleanup", "completed", "deliveries",
        ])
        transaction.on_commit(partial(worker.notify, row.pk))


def retry_cleanup(pk, publishers):
    """Undo again what a failed undo left behind; `publishers` must be open.
    Undoing talks to the network, so no row lock is held meanwhile."""
    row = PublicationEvent.objects.get(pk=pk)
    if not row.needs_cleanup:
        raise ActionRefused("it doesn't need cleaning up")
    row.needs_cleanup = False
    event = row.to_event()
    for publisher in worker.failed_publishers(row, publishers):
        worker.undo(row, publisher, event)
    configured = {p.name for p in publishers}
    gone = sorted({d["publisher"] for d in row.deliveries} - configured)
    if gone:
        row.needs_cleanup = True
        row.last_error += f"\nundo: no longer configured: {', '.join(gone)}"
    PublicationEvent.objects.filter(pk=pk, needs_cleanup=True).update(
        needs_cleanup=row.needs_cleanup, completed=row.completed, deliveries=row.deliveries, last_error=row.last_error,
    )
    if row.needs_cleanup:
        raise ActionRefused("something could not be undone, see its last error")


def mark_cleaned_up(pk, publishers, username):
    """For leftovers removed by hand, or that no longer exist: forget them, and
    note who did it, which releases the station."""
    with transaction.atomic():
        row = PublicationEvent.objects.select_for_update().get(pk=pk)
        if not row.needs_cleanup:
            raise ActionRefused("it doesn't need cleaning up")
        _forget_leftovers(row, publishers)
        row.needs_cleanup = False
        row.last_error += f"\nmarked as cleaned up by {username} at {worker.db_now():%Y-%m-%d %H:%M:%S %Z}"
        row.save(update_fields=["completed", "deliveries", "needs_cleanup", "last_error"])
