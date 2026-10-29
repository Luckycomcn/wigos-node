from django.test import TestCase

from api.models import WIGOSNodeUser
from publishing.base import Event, Operation

from .models import PublicationEvent

RECORD = {"id": "0-756-0-outbox", "properties": {"updated": "2026-10-29T09:00:00Z"}}


def make_row(**fields):
    values = {
        "operation": Operation.UPDATE,
        "station_id": 42,
        "wigos_identifier": "0-756-0-outbox",
        "wmdrv2": RECORD,
    }
    values.update(fields)
    return PublicationEvent.objects.create(**values)


class PublicationEventTestCase(TestCase):
    def test_defaults(self):
        row = make_row()
        self.assertEqual(row.status, PublicationEvent.Status.PENDING)
        self.assertEqual(row.source, PublicationEvent.Source.SYSTEM)
        self.assertEqual((row.attempts, row.completed, row.deliveries, row.issuers, row.ordering_keys), (0, [], [], [], []))
        self.assertIsNone(row.changed_by)
        self.assertIsNone(row.next_attempt_at)
        self.assertIsNotNone(row.created_at)

    def test_to_event(self):
        user = WIGOSNodeUser.objects.create(username="outbox", email="outbox@example.org")
        previous = {"id": "0-756-0-old"}
        row = make_row(previous_wmdrv2=previous, changed_by=user, source=PublicationEvent.Source.API)

        event = PublicationEvent.objects.get(pk=row.pk).to_event()

        self.assertEqual(event, Event(
            id=row.pk,
            operation=Operation.UPDATE,
            station_id=42,
            wigos_identifier="0-756-0-outbox",
            wmdrv2=RECORD,
            previous_wmdrv2=previous,
            changed_by=user.pk,
            source="api",
            occurred_at=row.created_at,
        ))
        self.assertIs(type(event.operation), Operation)

    def test_deleting_the_user_keeps_the_event(self):
        user = WIGOSNodeUser.objects.create(username="gone", email="gone@example.org")
        row = make_row(changed_by=user)
        user.delete()
        row.refresh_from_db()
        self.assertIsNone(row.changed_by)

    def test_events_by_issuer_and_ordering_key(self):
        swiss = make_row(issuers=["756"], ordering_keys=["station:1", "wsi:0-756-0-a"])
        moved = make_row(issuers=["756", "76"], ordering_keys=["station:2", "wsi:0-756-0-a", "wsi:0-76-0-a"])
        make_row(issuers=["76"], ordering_keys=["station:3"])

        self.assertQuerySetEqual(PublicationEvent.objects.filter(issuers__overlap=["756", "999"]), [swiss, moved])
        self.assertQuerySetEqual(PublicationEvent.objects.filter(ordering_keys__overlap=["wsi:0-756-0-a"]), [swiss, moved])
