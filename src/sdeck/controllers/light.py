"""Light card controller — light control via HA."""

from __future__ import annotations

from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller


@register_controller("light")
class LightController(BaseController):
    """Controls the LightCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.entity_name = config.get("entity", "upstairs")

    async def setup(self) -> None:
        """Wire encoder events to light brightness/color temp controls."""
        light = self.ha.light(self.entity_name)

        @self.card.on("brightness_up")
        async def _bright_up() -> None:
            state = light.state
            if state and state.attributes:
                current = state.attributes.get("brightness", 128)
                await light.set_brightness(min(255, current + 25))

        @self.card.on("brightness_down")
        async def _bright_down() -> None:
            state = light.state
            if state and state.attributes:
                current = state.attributes.get("brightness", 128)
                await light.set_brightness(max(0, current - 25))

        @self.card.on("toggle")
        async def _toggle() -> None:
            await light.toggle()

        light.on_state_change(lambda _old, _new: self._on_state_change())

    async def sync_state(self) -> None:
        """Sync card UI with current light state."""
        light = self.ha.light(self.entity_name)
        state = light.state
        self.card.set("state", state.state if state else "unavailable")
        if state and state.attributes:
            brightness = state.attributes.get("brightness", 0)
            self.card.set("brightness", int(brightness / 255 * 100))
            color_temp = state.attributes.get("color_temp")
            if color_temp is not None:
                self.card.set("color_temp", color_temp)

    def _on_state_change(self) -> None:
        import asyncio

        asyncio.ensure_future(self.sync_state())
