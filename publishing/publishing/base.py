"""Plugin interfaces.

A MessageGenerator turns an Event into Messages, a TransportLayer delivers
them, and a Publisher pairs one of each. Publishers run in their configured
order for every event.

The worker runs events in parallel threads and shares one instance of each
plugin between them, so plugins must be thread-safe (or keep per-thread
state themselves)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Operation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True)
class Event:
    """A committed station change, as queued in the outbox. Plugins only see
    this snapshot and never read or write stations themselves."""

    id: int
    operation: Operation
    station_id: int
    wigos_identifier: str
    wmdrv2: dict  # the record as stored when the change was made
    previous_wmdrv2: dict | None  # before an update, when known
    changed_by: int | None  # user id; None for superusers and the shell
    source: str  # "api", "admin" or "system"
    occurred_at: datetime


@dataclass(frozen=True)
class Message:
    body: bytes
    media_type: str
    name: str | None = None  # file name for storage transports
    topic: str | None = None  # overrides the transport's default topic
    headers: dict = field(default_factory=dict)


class PublishError(Exception):
    """A message could not be delivered. The worker retries the event later."""


class MessageGenerator(ABC):
    def __init__(self, **options):
        self.options = options

    @abstractmethod
    def generate(self, event: Event) -> list[Message]:
        """Messages for this event; [] if this generator ignores it (e.g. a
        record file generator on DELETE)."""


class TransportLayer(ABC):
    def __init__(self, **options):
        self.options = options

    def open(self):
        """Connect. Called once per worker before the first send."""

    def close(self):
        """Disconnect. Called once when the worker stops."""

    @abstractmethod
    def send(self, message: Message) -> None:
        """Deliver one message; raise PublishError on failure."""

    def send_many(self, messages: list[Message]) -> None:
        """Deliver messages in order. Override to send in bulk."""
        for message in messages:
            self.send(message)


class Publisher(ABC):
    """Pairs a generator with a transport. Subclasses decide which events
    they publish, and may override publish() for special flows."""

    def __init__(self, name: str, generator: MessageGenerator, transport: TransportLayer):
        self.name = name
        self.generator = generator
        self.transport = transport

    @abstractmethod
    def should_publish(self, event: Event) -> bool:
        """Whether this publisher handles the event at all."""

    def open(self):
        self.transport.open()

    def close(self):
        self.transport.close()

    def publish(self, event: Event) -> None:
        if not self.should_publish(event):
            return
        self.transport.send_many(self.generator.generate(event))


class DefaultPublisher(Publisher):
    """Publishes every event."""

    def should_publish(self, event: Event) -> bool:
        return True
