import unittest
from datetime import datetime, timezone

from publishing.base import (
    DefaultPublisher,
    Event,
    Message,
    MessageGenerator,
    Operation,
    Publisher,
    TransportLayer,
)


def make_event(operation=Operation.CREATE, **fields):
    values = {
        "id": 1,
        "operation": operation,
        "station_id": 7,
        "wigos_identifier": "0-20000-0-12345",
        "wmdrv2": {"id": "0-20000-0-12345"},
        "previous_wmdrv2": None,
        "changed_by": None,
        "source": "system",
        "occurred_at": datetime(2026, 10, 28, tzinfo=timezone.utc),
    }
    values.update(fields)
    return Event(**values)


class EchoGenerator(MessageGenerator):
    """One message per event, carrying the operation; none on DELETE."""

    def generate(self, event):
        if event.operation == Operation.DELETE:
            return []
        return [Message(body=event.operation.encode(), media_type="text/plain", name=event.wigos_identifier)]


class RecordingTransport(TransportLayer):
    def __init__(self, **options):
        super().__init__(**options)
        self.sent = []
        self.opened = self.closed = False

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def send(self, message):
        self.sent.append(message)


class CreatesOnlyPublisher(Publisher):
    def should_publish(self, event):
        return event.operation == Operation.CREATE


class PublisherTestCase(unittest.TestCase):
    def setUp(self):
        self.transport = RecordingTransport()
        self.publisher = DefaultPublisher("echo", EchoGenerator(), self.transport)

    def test_publish_sends_generated_messages(self):
        self.publisher.publish(make_event(Operation.UPDATE))
        self.assertEqual([m.body for m in self.transport.sent], [b"update"])
        self.assertEqual(self.transport.sent[0].name, "0-20000-0-12345")

    def test_generator_returning_nothing_sends_nothing(self):
        self.publisher.publish(make_event(Operation.DELETE))
        self.assertEqual(self.transport.sent, [])

    def test_should_publish_filters_events(self):
        publisher = CreatesOnlyPublisher("creates", EchoGenerator(), self.transport)
        publisher.publish(make_event(Operation.UPDATE))
        publisher.publish(make_event(Operation.CREATE))
        self.assertEqual([m.body for m in self.transport.sent], [b"create"])

    def test_open_and_close_reach_the_transport(self):
        self.publisher.open()
        self.publisher.close()
        self.assertTrue(self.transport.opened)
        self.assertTrue(self.transport.closed)

    def test_send_many_keeps_order(self):
        messages = [Message(body=str(i).encode(), media_type="text/plain") for i in range(3)]
        self.transport.send_many(messages)
        self.assertEqual(self.transport.sent, messages)

    def test_options_are_kept(self):
        self.assertEqual(RecordingTransport(topic="a/b").options, {"topic": "a/b"})

    def test_publisher_without_should_publish_is_abstract(self):
        class Incomplete(Publisher):
            pass

        with self.assertRaises(TypeError):
            Incomplete("x", EchoGenerator(), self.transport)
