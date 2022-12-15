import logging
import time

from prometheus_client import (
    GC_COLLECTOR,
    PLATFORM_COLLECTOR,
    PROCESS_COLLECTOR,
    REGISTRY,
    start_http_server,
)

from .collector import SkupperCollector
from .config import settings

log = logging.getLogger(__name__)


def config_logging() -> None:

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=settings.log_level.upper(),
    )


def app() -> None:
    """Main entry point for the application script"""
    REGISTRY.register(
        SkupperCollector(
            service_controller=settings.service_controller,
            timeout=settings.service_controller_timeout,
        )
    )
    # disable standard prometheus metrics
    REGISTRY.unregister(GC_COLLECTOR)
    REGISTRY.unregister(PLATFORM_COLLECTOR)
    REGISTRY.unregister(PROCESS_COLLECTOR)
    start_http_server(port=settings.port)
    while True:
        time.sleep(5)


if __name__ == "__main__":
    config_logging()
    log.info("Starting skupper-prometheus-collector")
    app()
