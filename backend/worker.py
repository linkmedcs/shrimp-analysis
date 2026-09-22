"""RQ worker process entry point."""

from __future__ import annotations

from rq import Queue, Worker

from .config import get_settings
from .queue import get_redis_connection


def main() -> None:
    settings = get_settings()
    connection = get_redis_connection()
    queue = Queue(settings.queue_name, connection=connection)
    Worker([queue], connection=connection).work()


if __name__ == "__main__":
    main()

