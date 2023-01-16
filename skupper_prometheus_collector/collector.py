import logging
import subprocess
from collections.abc import (
    Callable,
    Generator,
    Mapping,
)
from typing import Any

import requests
from prometheus_client import Metric
from prometheus_client.core import (
    GaugeMetricFamily,
    InfoMetricFamily,
)
from prometheus_client.registry import Collector

log = logging.getLogger(__name__)


def service_controller_stats(service_controller: str, timeout: int) -> dict[str, Any]:
    """Fetch stats (/DATA) from service controller pod."""
    try:
        log.debug(f"Fetching data from service controller {service_controller}")
        response = requests.get(service_controller, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError("Unable to fetch data from service controller") from exc

    return response.json()


def skupper_link_status(skupper_binary: str, timeout: int) -> str:
    """Fetch skupper link status from skupper-cli."""
    try:
        log.debug(f"Fetching skupper link status from {skupper_binary}")
        response = subprocess.run(
            [
                skupper_binary,
                "link",
                "status",
                "--wait",
                str(timeout),
                "--timeout",
                "0.01s",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Unable to fetch skupper link status") from exc

    return response.stdout


def link_status(skupper_link_status_output: str) -> list[tuple[str, bool]]:
    """Compile link statistics from skupper-cli."""
    parse_lines = False
    link_stats = []
    for line in skupper_link_status_output.splitlines():
        if line.startswith("---"):
            continue

        if line.startswith("Links created from this site"):
            # we found our section to parse
            parse_lines = True
            continue

        if parse_lines and line.startswith("There are no links configured or active"):
            break

        if parse_lines and line:
            # "Links created from this site" section
            link_name = line.split(" ")[1]
            active = True if "is active" in line else False
            link_stats.append((link_name, active))
            continue

        if parse_lines and not line:
            # end of "Links created from this site" section
            break

    return link_stats


class SkupperCollector(Collector):
    def __init__(
        self,
        service_controller: str,
        service_controller_timeout: int,
        skupper_binary: str,
        skupper_binary_timeout: int,
    ) -> None:
        self.service_controller = service_controller
        self.service_controller_timeout = service_controller_timeout
        self.skupper_binary = skupper_binary
        self.skupper_binary_timeout = skupper_binary_timeout

    def compile_service_controller_metrics(
        self, stats: Mapping[str, list[Mapping[str, Any]]]
    ) -> Generator[Metric, None, None]:
        """Compute prometheus metrics based on service-controller stats."""
        log.debug("Compiling service-controller metrics")
        sites = stats.get("sites", [])
        services = stats.get("services", [])
        # site metrics
        skupper_spec = InfoMetricFamily(
            name="skupper_site_spec",
            documentation="Skupper version and site information",
            labels=["site_name", "namespace"],
        )
        skupper_outgoing_connections = GaugeMetricFamily(
            name="skupper_site_outgoing_connections",
            documentation="Number of outgoing site connections",
            labels=["site_name", "namespace"],
        )
        log.debug(f"Compiling site metrics for {len(sites)} sites")
        for site in sites:
            skupper_spec.add_metric(
                [site["site_name"], site["namespace"]],
                {
                    "version": site["version"],
                    "site_id": site["site_id"],
                    "edge": "1" if site["edge"] else "0",
                    "gateway": "1" if site["gateway"] else "0",
                    "url": site["url"],
                },
            )
            skupper_outgoing_connections.add_metric(
                [site["site_name"], site["namespace"]], len(site["connected"])
            )

        log.debug("Compiling service metrics")
        # service metrics
        service_spec = InfoMetricFamily(
            name="skupper_service_spec", documentation="Service information"
        )
        for service in services:
            service_spec.add_metric(
                [], {"address": service["address"], "protocol": service["protocol"]}
            )
        skupper_service_count = GaugeMetricFamily(
            name="skupper_service_count",
            documentation="Number of available skupper services",
            value=len(services),
        )
        yield from [
            skupper_spec,
            skupper_outgoing_connections,
            service_spec,
            skupper_service_count,
        ]

    def compile_skupper_link_status_metrics(
        self, link_stats: list[tuple[str, bool]]
    ) -> Generator[Metric, None, None]:
        """Compute prometheus metrics based on skupper link status."""
        log.debug("Compiling skupper link status metrics")
        metric = GaugeMetricFamily(
            name="skupper_link_status",
            documentation="Status of skupper links",
            labels=["link_name"],
        )
        for link in link_stats:
            name, active = link
            metric.add_metric([name], value=1 if active else 0)
        yield metric

    def collect(
        self,
        fetch_service_controller_stats_func: Callable[
            [str, int], Mapping[str, list[Mapping[str, Any]]]
        ] = service_controller_stats,
    ) -> Generator[Metric, None, None]:
        stats = fetch_service_controller_stats_func(
            self.service_controller, self.service_controller_timeout
        )
        yield from self.compile_service_controller_metrics(stats)

        output = skupper_link_status(self.skupper_binary, self.skupper_binary_timeout)
        link_stats = link_status(output)
        yield from self.compile_skupper_link_status_metrics(link_stats)
