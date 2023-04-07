import json
from pathlib import Path

import httpretty as httpretty_module
import pytest

from skupper_prometheus_collector import collector


@pytest.fixture
def skupper_collector(fake_skupper_cli: str) -> collector.SkupperCollector:
    """Return a SkupperCollector instance."""
    return collector.SkupperCollector(
        "http://service-controller:1234", "token", "ca_file", 1, fake_skupper_cli, 1
    )


def test_service_controller_stats(httpretty: httpretty_module) -> None:
    """Test service_controller_stats."""
    url = "http://service-controller:1234/foobar"

    httpretty.register_uri(
        httpretty.GET, url, body=json.dumps({"key": "value"}), content_type="text/json"
    )
    assert collector.service_controller_stats(url, "token", "ca_file", 1) == {
        "key": "value"
    }


def test_skupper_collector_compile_metrics(
    skupper_collector: collector.SkupperCollector,
) -> None:
    """Test SkupperCollector.compile_metrics."""
    stats = json.loads((Path(__file__).parent / "fixtures/stats.json").read_text())
    metrics = list(skupper_collector.compile_service_controller_metrics(stats))
    assert len(metrics) == 4
    assert metrics[0].name == "skupper_site_spec"
    assert len(metrics[0].samples) == 2
    assert metrics[1].name == "skupper_site_outgoing_connections"
    assert len(metrics[1].samples) == 2
    assert metrics[2].name == "skupper_service_spec"
    assert len(metrics[2].samples) == 1
    assert metrics[3].name == "skupper_service_count"
    assert len(metrics[3].samples) == 1


def test_skupper_collector_collect(
    skupper_collector: collector.SkupperCollector,
) -> None:
    """Test SkupperCollector.collect."""

    def fake_request(url: str, token: str, ca_file: str, timeout: int) -> dict:
        return {"key": "value"}

    assert (
        len(
            list(
                skupper_collector.collect(
                    fetch_service_controller_stats_func=fake_request
                )
            )
        )
        == 5
    )


@pytest.mark.parametrize(
    "link_status_output, expected",
    [
        (
            """
Links created from this site:
-------------------------------
There are no links configured or active

Currently active links from other sites:
----------------------------------------
context deadline exceeded
""",
            [],
        ),
        (
            """
Links created from this site:
-------------------------------
Link site-01 is active

Currently active links from other sites:
----------------------------------------
context deadline exceeded
""",
            [("site-01", True)],
        ),
        (
            """
Links created from this site:
-------------------------------
Link site-01 is not active

Currently active links from other sites:
----------------------------------------
context deadline exceeded
""",
            [("site-01", False)],
        ),
        (
            """
Links created from this site:
-------------------------------
Link site-01 is active
Link site-02 is active

Currently active links from other sites:
----------------------------------------
context deadline exceeded
""",
            [("site-01", True), ("site-02", True)],
        ),
        (
            """
Links created from this site:
-------------------------------
Link site-01 is active
Link site-02 is not active

Currently active links from other sites:
----------------------------------------
context deadline exceeded
""",
            [("site-01", True), ("site-02", False)],
        ),
        (
            """
Links created from this site:
-------------------------------
Link site-01 is active
Link site-02 is not active
Link site-03 is active

Currently active links from other sites:
----------------------------------------
context deadline exceeded
""",
            [("site-01", True), ("site-02", False), ("site-03", True)],
        ),
    ],
)
def test_link_status(link_status_output: str, expected: list[tuple[str, bool]]) -> None:
    assert collector.link_status(link_status_output) == expected
