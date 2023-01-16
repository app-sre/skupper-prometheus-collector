from collections.abc import Generator
from pathlib import Path

import httpretty as httpretty_module
import pytest


@pytest.fixture()
def httpretty() -> Generator[httpretty_module, None, None]:
    with httpretty_module.enabled(allow_net_connect=False):
        httpretty_module.reset()
        yield httpretty_module


@pytest.fixture()
def fake_skupper_cli() -> str:
    return str(Path(__file__).parent / "bin" / "skupper")
