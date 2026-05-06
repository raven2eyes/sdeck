"""Light card controller — light control via upstream DeckUI LightCard."""

from __future__ import annotations

import logging
from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller

log = logging.getLogger(__name__)

_BRIGHTNESS_STEP = 25  # 0-255 per encoder tick
_KELVIN_STEP = 250  # kelvin per encoder tick


@register_controller("light")
class LightController(BaseController):
    """Controls the upstream LightCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.entity_name = config.get("entity", "upstairs")

    async def setup(self) -> None:
        """Wire encoder events to light brightness / kelvin / toggle."""
        light = self.ha.light(self.entity_name)

        @self.card.on("toggle")
        async def _toggle(*_args: Any) -> None:
            await light.toggle()

        @self.card.on("brightness_up")
        async def _bright_up(steps: int = 1, **_kw: Any) -> None:
            current = light.brightness or 0
            new_val = min(255, current + _BRIGHTNESS_STEP * steps)
            await light.set_brightness(new_val)

        @self.card.on("brightness_down")
        async def _bright_down(steps: int = 1, **_kw: Any) -> None:
            current = light.brightness or 0
            new_val = max(0, current - _BRIGHTNESS_STEP * abs(steps))
            await light.set_brightness(new_val)

        @self.card.on("kelvin_up")
        async def _kelvin_up(steps: int = 1, **_kw: Any) -> None:
            current = light.kelvin or light.min_kelvin or 2000
            max_k = light.max_kelvin or 6500
            new_val = min(max_k, current + _KELVIN_STEP * steps)
            await light.set_kelvin(new_val)

        @self.card.on("kelvin_down")
        async def _kelvin_down(steps: int = 1, **_kw: Any) -> None:
            current = light.kelvin or light.min_kelvin or 2000
            min_k = light.min_kelvin or 2000
            new_val = max(min_k, current - _KELVIN_STEP * abs(steps))
            await light.set_kelvin(new_val)

        light.on_state_change(self._on_state_change)

    async def sync_state(self) -> None:
        """Sync card UI with current light state."""
        light = self.ha.light(self.entity_name)
        is_on = light.state == "on"
        self.card.set("lights", is_on)

        brightness = light.brightness or 0
        pct = brightness / 255
        self.card.set("brightness", pct)
        self.card.set("brightness_value_text", f"{int(pct * 100)}%")

        kelvin = light.kelvin
        min_k = light.min_kelvin or 2000
        max_k = light.max_kelvin or 6500
        k_range = max_k - min_k or 1
        if kelvin is not None:
            k_pct = (kelvin - min_k) / k_range
            self.card.set("kelvin", k_pct)
            self.card.set("kelvin_value_text", f"{kelvin}K")
        else:
            self.card.set("kelvin", 0.0)
            self.card.set("kelvin_value_text", "")

    async def _on_state_change(
        self, _old: object = None, _new: object = None
    ) -> None:
        await self.sync_state()
        await self.card.request_refresh()
