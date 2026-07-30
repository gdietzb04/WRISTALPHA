"""APScheduler process for recurring local pipeline runs."""

from __future__ import annotations

import logging
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from wristalpha.config import RuntimeSettings
from wristalpha.operations.logging import configure_logging
from wristalpha.operations.pipeline import run_pipeline

LOGGER = logging.getLogger(__name__)


def main() -> None:
    settings = RuntimeSettings()
    configure_logging(settings.log_level)
    stopped = threading.Event()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_pipeline,
        "interval",
        hours=settings.schedule_interval_hours,
        args=[str(settings.config_path)],
        id="wristalpha-pipeline",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=900,
    )
    scheduler.start()
    run_pipeline(str(settings.config_path))

    def stop(signum: int, frame: object) -> None:
        del signum, frame
        stopped.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    LOGGER.info("scheduler started")
    stopped.wait()
    scheduler.shutdown(wait=True)
    LOGGER.info("scheduler stopped")


if __name__ == "__main__":
    main()
