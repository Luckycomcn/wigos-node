import logging

from ..base import TransportLayer

logger = logging.getLogger("publishing")


class LogTransport(TransportLayer):
    """Logs messages instead of delivering them; for development and tests.

    Options: topic (default topic, as a real transport would use it) and
    max_body (characters of the body to log, default 500; 0 logs none)."""

    def __init__(self, *, topic=None, max_body=500, **options):
        super().__init__(topic=topic, max_body=max_body, **options)
        self.topic = topic
        self.max_body = max_body

    def send(self, message):
        body = message.body.decode("utf-8", errors="replace")
        if len(body) > self.max_body:
            body = body[: self.max_body] + "..."
        logger.info(
            "publish name=%s topic=%s type=%s size=%d %s",
            message.name,
            message.topic or self.topic,
            message.media_type,
            len(message.body),
            body,
        )
