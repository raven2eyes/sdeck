"""Dashboard card controller — date/time, weather info, deck brightness."""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import TYPE_CHECKING, Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller

if TYPE_CHECKING:
    from deckui.runtime.deck import Deck

log = logging.getLogger(__name__)

_BRIGHTNESS_STEP = 0.05  # 5 % per encoder tick
_TIME_REFRESH_INTERVAL = 10  # seconds


@register_controller("dashboard")
class DashboardController(BaseController):
    """Controls the upstream DashboardCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.screens = config.get("screens", ["main"])
        self._deck: Deck | None = config.get("_deck")
        self._deck_brightness: float = 0.5
        self._temp_entity: str | None = config.get("temperature_entity")
        self._humidity_entity: str | None = config.get("humidity_entity")
        self._time_task: asyncio.Task[None] | None = None

    async def setup(self) -> None:
        """Wire encoder events and start the clock update loop."""
        # Read initial brightness from hardware if available
        if self._deck is not None:
            self._deck_brightness = self._deck.brightness / 100

        @self.card.on("brightness_up")
        async def _bright_up(steps: int = 1, **_kw: Any) -> None:
            self._deck_brightness = min(1.0, self._deck_brightness + _BRIGHTNESS_STEP * abs(steps))
            self.card.set("deck_brightness", self._deck_brightness)
            await self._apply_deck_brightness()

        @self.card.on("brightness_down")
        async def _bright_down(steps: int = 1, **_kw: Any) -> None:
            self._deck_brightness = max(0.0, self._deck_brightness - _BRIGHTNESS_STEP * abs(steps))
            self.card.set("deck_brightness", self._deck_brightness)
            await self._apply_deck_brightness()

        @self.card.on("next_screen")
        async def _next(*_args: Any) -> None:
            # Screen navigation handled at provisioner level
            pass

        # Wire weather sensors if configured
        if self._temp_entity:
            sensor = self.ha.sensor(self._temp_entity)
            sensor.on_state_change(self._on_temp_change)
        if self._humidity_entity:
            sensor = self.ha.sensor(self._humidity_entity)
            sensor.on_state_change(self._on_humidity_change)

        self._time_task = asyncio.create_task(self._clock_loop())

    async def sync_state(self) -> None:
        """Sync card UI with current date/time and sensor values."""
        self._update_datetime()
        self.card.set("deck_brightness", self._deck_brightness)
        await self._apply_deck_brightness()

        if self._temp_entity:
            sensor = self.ha.sensor(self._temp_entity)
            val = sensor.state
            if val and val not in ("unknown", "unavailable"):
                self.card.set("temperature", f"{val}°C")
        if self._humidity_entity:
            sensor = self.ha.sensor(self._humidity_entity)
            val = sensor.state
            if val and val not in ("unknown", "unavailable"):
                self.card.set("humidity", f"{val}%")

    def _update_datetime(self) -> None:
        now = datetime.datetime.now()
        self.card.set("time", now.strftime("%H:%M"))
        self.card.set("date", now.strftime("%A, %d %B"))

    async def _apply_deck_brightness(self) -> None:
        """Push brightness to the Stream Deck hardware."""
        if self._deck is not None:
            await self._deck.set_brightness(int(self._deck_brightness * 100))

    def _on_temp_change(self, _old: object = None, _new: object = None) -> None:
        sensor = self.ha.sensor(self._temp_entity)  # type: ignore[arg-type]
        val = sensor.state
        if val and val not in ("unknown", "unavailable"):
            self.card.set("temperature", f"{val}°C")
            asyncio.ensure_future(self.card.request_refresh())

    def _on_humidity_change(self, _old: object = None, _new: object = None) -> None:
        sensor = self.ha.sensor(self._humidity_entity)  # type: ignore[arg-type]
        val = sensor.state
        if val and val not in ("unknown", "unavailable"):
            self.card.set("humidity", f"{val}%")
            asyncio.ensure_future(self.card.request_refresh())

    async def _clock_loop(self) -> None:
        """Periodically update date and time on the card."""
        try:
            while True:
                self._update_datetime()
                await self.card.request_refresh()
                await asyncio.sleep(_TIME_REFRESH_INTERVAL)
        except asyncio.CancelledError:
            pass
