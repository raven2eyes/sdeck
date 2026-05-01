"""Timer card controller — timer control via HA."""

from __future__ import annotations

from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller


@register_controller("timer")
class TimerController(BaseController):
    """Controls the TimerCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.entity_name = config.get("entity", "streamdeck")

    async def setup(self) -> None:
        """Wire touch/encoder events to timer start/pause/cancel."""

        @self.card.on("start")
        async def _start() -> None:
            await self.ha.call_service(
                "timer", "start", entity_id=f"timer.{self.entity_name}"
            )

        @self.card.on("pause")
        async def _pause() -> None:
            await self.ha.call_service(
                "timer", "pause", entity_id=f"timer.{self.entity_name}"
            )

        @self.card.on("cancel")
        async def _cancel() -> None:
            await self.ha.call_service(
                "timer", "cancel", entity_id=f"timer.{self.entity_name}"
            )

        @self.card.on("adjust")
        async def _adjust() -> None:
            # Placeholder for encoder-based duration adjustment
            pass

    async def sync_state(self) -> None:
        """Sync card UI with current timer state."""
        sensor = self.ha.sensor(self.entity_name)
        state = sensor.state
        self.card.set("state", state.state if state else "idle")
        if state and state.attributes:
            remaining = state.attributes.get("remaining")
            if remaining:
                self.card.set("remaining", remaining)
