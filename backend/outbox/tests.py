import base64
import copy
import hashlib
import json
import threading
import time
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from api import stations
from api.models import Station, WIGOSNodeGroup, WIGOSNodeUser
from publishing.base import (
    DefaultPublisher,
    Event,
    Location,
    Message,
    MessageGenerator,
    Operation,
    PublishError,
    TransportLayer,
)
from publishing.generators.wmdr2 import RecordFileGenerator
from publishing.generators.wnm import WNMGenerator
from publishing.registry import ConfigurationError

from . import worker
from .checks import check_publishers
from .models import PublicationEvent
from .publishers import get_publishers

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


with open("/test_data/test_wmdrv2.json") as f:
    BASE_RECORD = json.load(f)


def record(wsi, title="Outbox station"):
    data = copy.deepcopy(BASE_RECORD)
    data["id"] = wsi
    data["properties"]["title"] = title
    return data


class QueueOnStationChangeTestCase(APITestCase):
    """Every committed station change leaves exactly one event; nothing that
    is rolled back does."""

    def setUp(self):
        # issuer groups seeded by api migration 0004
        self.member = WIGOSNodeUser.objects.create_user(username="ob_member", email="ob_member@example.com", password="pw")
        self.member.groups.add(WIGOSNodeGroup.objects.get(issuer_identifier=756).group)
        self.admin = WIGOSNodeUser.objects.create_superuser(username="ob_admin", email="ob_admin@example.com", password="pw")
        PublicationEvent.objects.all().delete()

    def events(self):
        return list(PublicationEvent.objects.order_by("id"))

    def test_create_queues_one_event(self):
        station = stations.create_station(self.member, record("0-756-0-ob1"))

        [event] = self.events()
        self.assertEqual(event.operation, Operation.CREATE)
        self.assertEqual(event.station_id, station.pk)
        self.assertEqual(event.wigos_identifier, "0-756-0-ob1")
        self.assertEqual(event.wmdrv2, station.wmdrv2)
        self.assertIsNone(event.previous_wmdrv2)
        self.assertEqual((event.source, event.changed_by), ("api", self.member))
        self.assertEqual(event.issuers, ["756"])
        self.assertEqual(event.ordering_keys, [f"station:{station.pk}", "wsi:0-756-0-ob1"])
        self.assertEqual(event.status, PublicationEvent.Status.PENDING)

    def test_update_keeps_the_previous_record(self):
        station = stations.create_station(self.member, record("0-756-0-ob2", "Old"))
        stations.update_station(self.member, station, record("0-756-0-ob2", "New"))

        create, update = self.events()
        self.assertEqual(update.operation, Operation.UPDATE)
        self.assertEqual(update.previous_wmdrv2["properties"]["title"], "Old")
        self.assertEqual(update.wmdrv2["properties"]["title"], "New")

    def test_wsi_moving_issuer_keys_both(self):
        station = stations.create_station(self.admin, record("0-756-0-ob3"))
        stations.update_station(self.admin, station, record("0-76-0-ob3"))

        update = self.events()[-1]
        self.assertEqual((update.source, update.changed_by), ("admin", None))
        self.assertEqual(update.wigos_identifier, "0-76-0-ob3")
        self.assertEqual(update.issuers, ["756", "76"])
        self.assertEqual(update.ordering_keys, [f"station:{station.pk}", "wsi:0-756-0-ob3", "wsi:0-76-0-ob3"])

    def test_delete_queues_a_deletion_that_outlives_the_station(self):
        station = stations.create_station(self.member, record("0-756-0-ob4"))
        pk = station.pk
        station.delete()

        deletion = self.events()[-1]
        self.assertEqual(deletion.operation, Operation.DELETE)
        self.assertEqual(deletion.station_id, pk)
        self.assertEqual(deletion.source, "system")
        self.assertFalse(Station.objects.filter(pk=pk).exists())

    def test_attribution_is_not_carried_to_a_later_save(self):
        station = stations.create_station(self.member, record("0-756-0-ob5"))
        station.save()  # e.g. a script, without stations.update_station
        self.assertEqual([(e.source, e.changed_by) for e in self.events()], [("api", self.member), ("system", None)])

    def test_rejected_save_queues_nothing(self):
        stations.create_station(self.member, record("0-756-0-ob6"))
        with self.assertRaises(stations.StationError):
            stations.create_station(self.member, record("0-756-0-ob6"))  # WSI taken
        self.assertEqual(len(self.events()), 1)

    def post_batch(self, updates, dry_run=False):
        self.client.force_authenticate(self.member)
        return self.client.post(reverse("wmdrv2-batch"), {"dry_run": dry_run, "updates": updates}, format="json")

    def test_batch_dry_run_queues_nothing(self):
        station = stations.create_station(self.member, record("0-756-0-ob7"))
        PublicationEvent.objects.all().delete()

        response = self.post_batch([{"station_id": station.pk, "wmdrv2": record("0-756-0-ob7", "New")}], dry_run=True)

        self.assertEqual(response.json()["summary"], {"ok": 1, "error": 0})
        self.assertEqual(self.events(), [])

    def test_batch_queues_only_the_accepted_updates(self):
        ok = stations.create_station(self.member, record("0-756-0-ob8"))
        other = stations.create_station(self.member, record("0-756-0-ob9"))
        PublicationEvent.objects.all().delete()

        response = self.post_batch([
            {"station_id": ok.pk, "wmdrv2": record("0-756-0-ob8", "New")},
            {"station_id": other.pk, "wmdrv2": record("0-756-0-ob8", "Clash")},  # WSI of the first station
        ])

        self.assertEqual(response.json()["summary"], {"ok": 1, "error": 1})
        self.assertEqual([(e.station_id, e.operation) for e in self.events()], [(ok.pk, Operation.UPDATE)])


LOG = "publishing.transports.log.LogTransport"
BROKEN = [
    {"NAME": "files", "GENERATOR": {"CLASS": "publishing.generators.wmdr2.RecordFileGenerator"}, "TRANSPORT": {"CLASS": LOG}},
    {"NAME": "files", "GENERATOR": {"CLASS": "nowhere.Generator"}, "TRANSPORT": {"CLASS": LOG}},
]


class PublishersSettingTestCase(SimpleTestCase):
    def test_configured_publishers_build(self):
        self.assertEqual(check_publishers(None), [])
        storage, wnm = get_publishers()
        self.assertEqual((storage.name, wnm.name), ("wis2-storage", "wis2-wnm"))
        self.assertIsInstance(storage.generator, RecordFileGenerator)
        self.assertIsInstance(wnm.generator, WNMGenerator)

    def test_publishers_are_built_once(self):
        self.assertIs(get_publishers()[0], get_publishers()[0])

    @override_settings(PUBLISHERS=BROKEN)
    def test_check_reports_every_problem(self):
        errors = check_publishers(None)
        self.assertEqual([e.id for e in errors], ["outbox.E001", "outbox.E001"])
        self.assertIn("centre_id", errors[0].msg)
        self.assertIn("NAME is used more than once", errors[1].msg)
        with self.assertRaises(ConfigurationError):
            get_publishers()

    def test_changed_setting_rebuilds(self):
        default = get_publishers()
        with override_settings(PUBLISHERS=[]):
            self.assertEqual(get_publishers(), [])
        self.assertEqual([p.name for p in get_publishers()], [p.name for p in default])

    @override_settings()
    def test_missing_setting_means_no_publishers(self):
        from django.conf import settings

        del settings.PUBLISHERS
        # deleting a setting sends no setting_changed, so reset by hand
        get_publishers.cache_clear()
        self.addCleanup(get_publishers.cache_clear)
        self.assertEqual(check_publishers(None), [])
        self.assertEqual(get_publishers(), [])


class MemoryStorage(TransportLayer):
    """Stores files in a dict at mem://store/<name>."""

    def __init__(self):
        super().__init__()
        self.files = {}
        self.puts = 0
        self.fail_remove = False

    def send(self, message):
        self.puts += 1
        url = f"mem://store/{message.name}"
        self.files[url] = message.body
        return Location(url)

    def remove(self, location):
        if self.fail_remove:
            raise PublishError("storage down")
        del self.files[location.url]


class MemoryBroker(TransportLayer):
    """Keeps the sent WNMs; refuses the next `failures` sends."""

    def __init__(self):
        super().__init__()
        self.sent = []
        self.failures = 0

    def send(self, message):
        if self.failures:
            self.failures -= 1
            raise PublishError("broker down")
        self.sent.append(json.loads(message.body))
        return None


class MemoryRetrievalPublisher(DefaultPublisher):
    def __init__(self, *args, storage, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = storage

    def retrieve(self, location):
        return self.storage.files[location.url]


class BrokenGenerator(MessageGenerator):
    def generate(self, event, deliveries):
        raise RuntimeError("boom")


KEYS = ["station:42", "wsi:0-756-0-outbox"]


class WorkerTestCase(TestCase):
    def setUp(self):
        PublicationEvent.objects.all().delete()
        self.storage = MemoryStorage()
        self.broker = MemoryBroker()
        self.publishers = [
            DefaultPublisher("files", RecordFileGenerator(centre_id="io-test"), self.storage),
            MemoryRetrievalPublisher("wnm", WNMGenerator(centre_id="io-test"), self.broker, storage=self.storage),
        ]

    def process_due(self):
        PublicationEvent.objects.filter(status=PublicationEvent.Status.PENDING).update(next_attempt_at=None)
        return worker.process_next(self.publishers)

    def test_publishes_the_file_then_its_wnm(self):
        row = make_row(operation=Operation.CREATE, ordering_keys=KEYS)

        self.assertTrue(worker.process_next(self.publishers))

        row.refresh_from_db()
        self.assertEqual(row.status, PublicationEvent.Status.PROCESSED)
        self.assertEqual(row.completed, ["files", "wnm"])
        self.assertIsNotNone(row.finished_at)
        url = row.deliveries[0]["url"]
        self.assertEqual(row.deliveries, [
            {"publisher": "files", "name": url.removeprefix("mem://store/"), "media_type": "application/geo+json",
             "topic": None, "url": url, "internal_url": None},
            {"publisher": "wnm", "name": None, "media_type": "application/geo+json",
             "topic": None, "url": None, "internal_url": None},
        ])
        [wnm] = self.broker.sent
        self.assertEqual((wnm["links"][0]["href"], wnm["links"][0]["rel"]), (url, "canonical"))
        digest = base64.b64encode(hashlib.sha512(self.storage.files[url]).digest()).decode()
        self.assertEqual(wnm["properties"]["integrity"]["value"], digest)
        self.assertFalse(worker.process_next(self.publishers))

    def test_retry_skips_completed_publishers_and_reuses_the_stored_file(self):
        row = make_row(ordering_keys=KEYS)
        self.broker.failures = 1

        with self.assertLogs("outbox", "WARNING"):
            worker.process_next(self.publishers)

        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts, row.completed), (PublicationEvent.Status.PENDING, 1, ["files"]))
        self.assertIn("wnm: broker down", row.last_error)
        self.assertGreater(row.next_attempt_at, timezone.now())
        self.assertFalse(worker.process_next(self.publishers))  # not due yet

        self.assertTrue(self.process_due())

        row.refresh_from_db()
        self.assertEqual(row.status, PublicationEvent.Status.PROCESSED)
        self.assertEqual(self.storage.puts, 1)
        self.assertEqual(self.broker.sent[0]["links"][0]["href"], row.deliveries[0]["url"])

    def test_retry_delay_doubles_up_to_an_hour(self):
        self.assertEqual([worker.retry_delay(n) for n in (1, 2, 3)], [timedelta(seconds=s) for s in (30, 60, 120)])
        self.assertEqual(worker.retry_delay(20), timedelta(hours=1))

    def test_gives_up_after_the_last_attempt_and_removes_the_stored_file(self):
        row = make_row(ordering_keys=KEYS)
        self.broker.failures = 99

        with self.assertLogs("outbox", "WARNING"):
            for _ in range(worker.MAX_ATTEMPTS):
                self.process_due()

        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts), (PublicationEvent.Status.FAILED, worker.MAX_ATTEMPTS))
        self.assertEqual((row.completed, row.deliveries), ([], []))
        self.assertIsNotNone(row.finished_at)
        self.assertEqual(self.storage.files, {})
        self.assertFalse(self.process_due())  # failed events aren't retried

    def test_a_failing_undo_is_recorded_and_the_event_stays_failed(self):
        row = make_row(ordering_keys=KEYS)
        self.broker.failures = 99
        self.storage.fail_remove = True

        with self.assertLogs("outbox", "WARNING"):
            for _ in range(worker.MAX_ATTEMPTS):
                self.process_due()

        row.refresh_from_db()
        self.assertEqual(row.status, PublicationEvent.Status.FAILED)
        self.assertIn("undo files: storage down", row.last_error)
        self.assertEqual(row.completed, ["files"])  # the file may still be stored
        self.assertEqual([d["publisher"] for d in row.deliveries], ["files"])
        self.assertEqual(len(self.storage.files), 1)

    def test_a_crashing_plugin_counts_as_a_failed_attempt(self):
        row = make_row(ordering_keys=KEYS)
        publishers = [DefaultPublisher("broken", BrokenGenerator(), self.broker)]

        with self.assertLogs("outbox", "WARNING"):
            worker.process_next(publishers)

        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts), (PublicationEvent.Status.PENDING, 1))
        self.assertIn("broken: boom", row.last_error)

    def test_deletion_links_to_the_last_processed_file_and_keeps_it(self):
        create = make_row(operation=Operation.CREATE, ordering_keys=KEYS)
        worker.process_next(self.publishers)
        deletion = make_row(operation=Operation.DELETE, ordering_keys=KEYS)

        worker.process_next(self.publishers)

        create.refresh_from_db()
        deletion.refresh_from_db()
        self.assertEqual(deletion.status, PublicationEvent.Status.PROCESSED)
        link = self.broker.sent[1]["links"][0]
        self.assertEqual((link["href"], link["rel"]), (create.deliveries[0]["url"], "deletion"))
        self.assertEqual([d["publisher"] for d in deletion.deliveries], ["wnm"])  # the file is create's
        self.assertEqual(self.storage.puts, 1)
        self.assertIn(create.deliveries[0]["url"], self.storage.files)

    def later(self):
        return timezone.now() + timedelta(hours=1)

    def test_a_station_waits_for_its_older_events(self):
        make_row(ordering_keys=["station:1", "wsi:a"], next_attempt_at=self.later())  # retrying
        make_row(ordering_keys=["station:1", "wsi:a"])
        other = make_row(ordering_keys=["station:2", "wsi:b"])
        self.assertEqual(worker.claim(), other)

    def test_order_is_kept_across_a_wsi_change(self):
        make_row(ordering_keys=["station:1", "wsi:a", "wsi:b"], next_attempt_at=self.later())  # a renamed to b
        make_row(ordering_keys=["station:1", "wsi:b"])
        self.assertIsNone(worker.claim())

    def test_a_moved_wsi_waits_for_the_station_it_left(self):
        left = make_row(ordering_keys=["station:1", "wsi:a"], next_attempt_at=self.later())
        joined = make_row(ordering_keys=["station:2", "wsi:a", "wsi:c"])
        self.assertIsNone(worker.claim())

        left.status = PublicationEvent.Status.PROCESSED
        left.save()
        self.assertEqual(worker.claim(), joined)

    def test_a_cleaned_up_failed_event_releases_its_station(self):
        make_row(ordering_keys=["station:1"], status=PublicationEvent.Status.FAILED)
        later = make_row(ordering_keys=["station:1"])
        self.assertEqual(worker.claim(), later)

    def test_a_failed_event_with_leftovers_holds_back_its_station(self):
        make_row(ordering_keys=["station:1"], status=PublicationEvent.Status.FAILED, completed=["files"])
        make_row(ordering_keys=["station:1"])
        self.assertIsNone(worker.claim())

    def test_the_next_change_goes_ahead_once_a_failed_event_is_undone(self):
        failed = make_row(ordering_keys=KEYS)
        later = make_row(ordering_keys=KEYS)
        self.broker.failures = worker.MAX_ATTEMPTS

        with self.assertLogs("outbox", "WARNING"):
            for _ in range(worker.MAX_ATTEMPTS):
                self.process_due()
        self.assertTrue(self.process_due())

        failed.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual((failed.status, failed.completed), (PublicationEvent.Status.FAILED, []))
        self.assertEqual(later.status, PublicationEvent.Status.PROCESSED)

    def test_claiming_takes_a_lease(self):
        row = make_row(ordering_keys=KEYS)

        self.assertEqual(worker.claim(), row)

        row.refresh_from_db()
        self.assertEqual(row.status, PublicationEvent.Status.PROCESSING)
        self.assertGreater(row.locked_until, timezone.now())
        self.assertIsNone(worker.claim())  # held by the lease

    def test_leases_follow_the_database_clock(self):
        row = make_row(ordering_keys=KEYS)
        worker.claim()
        # a worker whose clock runs a day ahead still sees the lease as held
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
            self.assertIsNone(worker.claim())
        row.refresh_from_db()
        self.assertAlmostEqual(row.locked_until, worker.db_now() + worker.LEASE, delta=timedelta(seconds=5))

    def test_finishing_drops_the_lease(self):
        row = make_row(ordering_keys=KEYS)
        worker.process_next(self.publishers)
        row.refresh_from_db()
        self.assertEqual((row.status, row.locked_until), (PublicationEvent.Status.PROCESSED, None))

    def store_record_file(self, row):
        """As if the storage publisher ran before the worker crashed."""
        [delivery] = self.publishers[0].publish(row.to_event(), [])
        PublicationEvent.objects.filter(pk=row.pk).update(
            completed=["files"], deliveries=[worker.dump_delivery(delivery)]
        )

    def crashed_row(self, attempts):
        row = make_row(
            ordering_keys=KEYS,
            status=PublicationEvent.Status.PROCESSING,
            locked_until=timezone.now() - timedelta(seconds=1),
            attempts=attempts,
        )
        self.store_record_file(row)
        return row

    def test_a_crashed_event_is_reclaimed_and_resumed(self):
        row = self.crashed_row(attempts=0)

        with self.assertLogs("outbox", "WARNING"):
            self.assertTrue(worker.process_next(self.publishers))

        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts), (PublicationEvent.Status.PROCESSED, 1))
        self.assertIn("lease expired", row.last_error)
        self.assertEqual(self.storage.puts, 1)  # not stored again
        self.assertEqual(self.broker.sent[0]["links"][0]["href"], row.deliveries[0]["url"])

    def test_a_crash_on_the_last_attempt_is_undone(self):
        row = self.crashed_row(attempts=worker.MAX_ATTEMPTS - 1)

        with self.assertLogs("outbox", "WARNING"):
            worker.process_next(self.publishers)

        row.refresh_from_db()
        self.assertEqual((row.status, row.attempts), (PublicationEvent.Status.FAILED, worker.MAX_ATTEMPTS))
        self.assertEqual((row.completed, row.deliveries), ([], []))
        self.assertEqual(self.storage.files, {})
        self.assertEqual(self.broker.sent, [])

    def test_a_worker_that_lost_its_lease_stops(self):
        row = make_row(ordering_keys=KEYS)
        claimed = worker.claim()
        # the lease expired and another worker claimed the event again
        PublicationEvent.objects.filter(pk=row.pk).update(locked_until=timezone.now() + timedelta(minutes=9))

        with self.assertRaises(worker.LeaseLost):
            worker.process(claimed, self.publishers)

        row.refresh_from_db()
        self.assertEqual(row.completed, [])  # nothing written by the old worker


class EventIdGenerator(MessageGenerator):
    def generate(self, event, deliveries):
        return [Message(body=str(event.id).encode(), media_type="text/plain")]


class TogetherTransport(TransportLayer):
    """Fails unless two sends happen at the same time."""

    def __init__(self):
        super().__init__()
        self.barrier = threading.Barrier(2, timeout=10)

    def send(self, message):
        try:
            self.barrier.wait()
        except threading.BrokenBarrierError:
            raise PublishError("sent alone")


class OverlapTransport(TransportLayer):
    """Slow sends, recording their order and the most that ran at once."""

    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.active = self.most_active = self.opened = self.closed = 0
        self.order = []

    def open(self):
        self.opened += 1

    def close(self):
        self.closed += 1

    def send(self, message):
        with self.lock:
            self.active += 1
            self.most_active = max(self.most_active, self.active)
        time.sleep(0.1)
        with self.lock:
            self.active -= 1
            self.order.append(int(message.body))


class ParallelWorkerTestCase(TransactionTestCase):
    """Real threads with their own connections, so rows must be committed.

    These tests need none of the data seeded by migrations. The flush after
    each one removes it, which is fine because Django runs TransactionTestCases
    after every TestCase. (serialized_rollback can't restore it: the api Group
    post_save receiver doesn't skip raw saves.)"""

    def statuses(self):
        return set(PublicationEvent.objects.values_list("status", flat=True))

    def test_unrelated_stations_are_published_at_the_same_time(self):
        make_row(ordering_keys=["station:1", "wsi:a"])
        make_row(ordering_keys=["station:2", "wsi:b"])

        worker.run([DefaultPublisher("together", EventIdGenerator(), TogetherTransport())], once=True, workers=2)

        self.assertEqual(self.statuses(), {PublicationEvent.Status.PROCESSED})

    def test_related_events_never_run_at_the_same_time(self):
        rows = [
            make_row(ordering_keys=["station:1", "wsi:a"]),
            make_row(ordering_keys=["station:1", "wsi:a", "wsi:b"]),  # a renamed to b
            make_row(ordering_keys=["station:2", "wsi:b"]),  # b moved to station 2
        ]
        transport = OverlapTransport()

        worker.run([DefaultPublisher("slow", EventIdGenerator(), transport)], once=True, workers=3)

        self.assertEqual(self.statuses(), {PublicationEvent.Status.PROCESSED})
        self.assertEqual(transport.most_active, 1)
        self.assertEqual(transport.order, [row.pk for row in rows])
        self.assertEqual((transport.opened, transport.closed), (1, 1))  # shared by the threads

    def test_run_once_processes_the_queue_with_the_configured_publishers(self):
        make_row(operation=Operation.CREATE, ordering_keys=["station:1"])
        make_row(operation=Operation.CREATE, ordering_keys=["station:2"])

        with self.assertLogs("publishing", "INFO"):
            call_command("run_publishers", "--once")

        self.assertEqual(self.statuses(), {PublicationEvent.Status.PROCESSED})
