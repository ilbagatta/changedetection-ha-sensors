"""Fixture comuni: server changedetection.io finto."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.changedetection_ha_sensors.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, DOMAIN

URL = "http://cd.local:5000"
NOW = 1_795_000_000

HELMET = "11111111-1111-1111-1111-111111111111"
PLUG = "22222222-2222-2222-2222-222222222222"
PAGE = "33333333-3333-3333-3333-333333333333"


class FakeServer:
    """Watch e rilevazioni in memoria; i test li modificano per simulare i cambi."""

    def __init__(self) -> None:
        self.watches: dict[str, dict[str, Any]] = {
            HELMET: {
                "title": "Casco",
                "url": "https://shop.example/casco",
                "last_changed": NOW - 3600,
                "last_checked": NOW,
                "last_error": False,
                "viewed": False,
                "paused": False,
            },
            PLUG: {
                "title": "Presa | smart",
                "url": "https://shop.example/presa",
                "last_changed": NOW - 86400 * 3,
                "last_checked": NOW,
                "last_error": False,
                "viewed": True,
                "paused": False,
            },
            PAGE: {
                "title": None,
                "url": "https://news.example/",
                "last_changed": NOW - 60,
                "last_checked": NOW,
                "last_error": "Timeout",
                "viewed": True,
                "paused": False,
            },
        }
        self.history: dict[str, dict[str, str]] = {
            HELMET: {
                str(NOW - 9000): "In Stock: True - Price: 229.95",
                str(NOW - 7000): "In Stock: False - Price: 229.95",
                str(NOW - 3600): "In Stock: True - Price: 319.95",
            },
            PLUG: {str(NOW - 86400 * 5): "€23.99 €12.00", str(NOW - 86400 * 3): "€22.79 €11.40"},
            PAGE: {str(NOW - 60): "Nuovo articolo\npubblicato"},
        }
        self.snapshot_calls = 0
        self.client = AsyncMock()
        self.client.async_get_watches.side_effect = lambda: {k: dict(v) for k, v in self.watches.items()}
        self.client.async_get_history.side_effect = self._history
        self.client.async_get_snapshot.side_effect = self._snapshot
        self.client.async_system_info.return_value = {"version": "0.55.7", "watch_count": 3}

    async def _history(self, uuid: str) -> list[str]:
        return sorted(self.history.get(uuid, {}), key=int, reverse=True)

    async def _snapshot(self, uuid: str, ts: str = "latest") -> str:
        self.snapshot_calls += 1
        return self.history[uuid][ts]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Carica custom_components/ in ogni test."""


@pytest.fixture
def server() -> Generator[FakeServer]:
    fake = FakeServer()
    with (
        patch("custom_components.changedetection_ha_sensors.ChangedetectionClient", return_value=fake.client),
        patch(
            "custom_components.changedetection_ha_sensors.config_flow.ChangedetectionClient", return_value=fake.client
        ),
    ):
        yield fake


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Changedetection.io",
        unique_id=URL,
        data={CONF_URL: URL, CONF_API_KEY: "test-key", CONF_VERIFY_SSL: True},
    )
