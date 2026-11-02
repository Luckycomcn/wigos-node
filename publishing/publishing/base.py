"""Plugin interfaces.

A MessageGenerator turns an Event into Messages and a TransportLayer delivers
them. A Publisher is one publishing process from start to end: an ordered list
of Steps, each pairing a generator with a transport. Each step gets the
Deliveries (receipts) of the steps before it in the same publisher. Publishers
know nothing about each other, and one failing doesn't affect the others.

Byte-level consistency: a storage transport returns the Location of what it
stored. Before a generator that needs_content() runs, its Publisher
retrieves every earlier Location and hands over the file actually served, so
e.g. a WNM's integrity always describes the stored file.

The worker runs events in parallel threads and shares one instance of each
plugin between them, so plugins must be thread-safe (or keep per-thread
state themselves)."""

import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
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


@dataclass(frozen=True)
class Location:
    """Where a storage transport put a message."""

    url: str  # public link, e.g. a WNM href
    internal_url: str | None = None  # where this node retrieves it; default url

    @property
    def retrieve_url(self):
        return self.internal_url or self.url


@dataclass(frozen=True)
class Delivery:
    """Receipt of one sent message, handed to the later steps of its publisher."""

    publisher: str  # name of the publisher that sent it
    message: Message
    location: Location | None = None  # storage transports only
    content: bytes | None = None  # the file retrieved from location, see needs_content()
    step: str | None = None  # name of the step that sent it


class PublishError(Exception):
    """A message could not be delivered. The worker marks the event failed;
    retrying it is up to a user."""


class MessageGenerator(ABC):
    def __init__(self, **options):
        self.options = options

    def needs_content(self, event: Event) -> bool:
        """True to get the earlier deliveries with `content` filled in."""
        return False

    @abstractmethod
    def generate(self, event: Event, deliveries: list[Delivery]) -> list[Message]:
        """Messages for this event; [] if this generator ignores it (e.g. a
        record file generator on DELETE). `deliveries` are the receipts of
        the steps that ran before this one in the same publisher."""


class TransportLayer(ABC):
    def __init__(self, **options):
        self.options = options

    def open(self):
        """Connect. Called once per worker before the first send."""

    def close(self):
        """Disconnect. Called once when the worker stops."""

    @abstractmethod
    def send(self, message: Message) -> Location | None:
        """Deliver one message and return where it is stored, if anywhere
        (storage transports); raise PublishError on failure.

        All or nothing: either the message is delivered completely, or
        nothing is left behind (e.g. write a temp file, then rename). A
        transport that can't promise this removes its partial output before
        raising."""

    def remove(self, location: Location) -> None:
        """Remove what send() stored at `location`, when a failed event is
        undone. Default: nothing to remove (e.g. notification transports)."""

    def send_many(self, messages: list[Message]) -> list[Location | None]:
        """Deliver messages in order. Override to send in bulk."""
        return [self.send(message) for message in messages]


@dataclass(frozen=True)
class Step:
    """One stage of a publisher: what to generate, and how to deliver it."""

    name: str  # unique within its publisher
    generator: MessageGenerator
    transport: TransportLayer


class Publisher(ABC):
    """One publishing process from start to end, and the coordinating instance
    of its steps: it runs them in order and feeds each generator what it needs.
    Subclasses decide which events they publish, and may override publish() for
    special flows."""

    retrieve_timeout = 30  # seconds

    def __init__(self, name: str, steps: list[Step]):
        self.name = name
        self.steps = list(steps)

    @abstractmethod
    def should_publish(self, event: Event) -> bool:
        """Whether this publisher handles the event at all."""

    def open(self):
        for step in self.steps:
            step.transport.open()

    def close(self):
        for step in reversed(self.steps):
            step.transport.close()

    def retrieve(self, location: Location) -> bytes:
        """The file served at the location's internal URL."""
        try:
            with urllib.request.urlopen(location.retrieve_url, timeout=self.retrieve_timeout) as response:
                return response.read()
        except (OSError, ValueError) as e:  # URLError and HTTPError are OSErrors
            raise PublishError(f"Could not retrieve {location.retrieve_url}: {e}") from e

    def run_step(self, step: Step, event: Event, deliveries: list[Delivery]) -> list[Delivery]:
        """Run one generator and its transport; returns the step's receipts."""
        if step.generator.needs_content(event):
            deliveries = [
                replace(d, content=self.retrieve(d.location)) if d.location else d
                for d in deliveries
            ]
        messages = step.generator.generate(event, deliveries)
        locations = step.transport.send_many(messages)
        return [Delivery(self.name, m, location, step=step.name) for m, location in zip(messages, locations)]

    def publish(self, event: Event, deliveries: list[Delivery] = (), *, done=(), previous=(), on_step=None) -> list[Delivery]:
        """Run the steps not yet `done` (step names) in order, stopping at the
        first error, and return all of this publisher's receipts for the event.

        `deliveries` are its receipts so far, for resuming; `previous` are its
        receipts from the station's last change; on_step(step, receipts) is
        called after each step so that the progress can be saved."""
        if not self.should_publish(event):
            return []
        deliveries = list(deliveries)
        # a deletion stores nothing: it refers to what the last change stored
        earlier = list(previous) if event.operation == Operation.DELETE else []
        for step in self.steps:
            if step.name in done:
                continue
            deliveries += self.run_step(step, event, earlier + deliveries)
            if on_step:
                on_step(step, deliveries)
        return deliveries

    def undo(self, event: Event, deliveries: list[Delivery]) -> None:
        """Remove what this publisher stored for an event that gave up, newest
        first. Errors are left to the caller to record."""
        transports = {step.name: step.transport for step in self.steps}
        for delivery in reversed(deliveries):
            if delivery.publisher == self.name and delivery.location:
                transports[delivery.step].remove(delivery.location)


class DefaultPublisher(Publisher):
    """Publishes every event."""

    def should_publish(self, event: Event) -> bool:
        return True
