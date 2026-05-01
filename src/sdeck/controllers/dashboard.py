"""Dashboard card controller — screen navigation and info display."""

from __future__ import annotations

from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller


@register_controller("dashboard")
class DashboardController(BaseController):
    """Controls the DashboardCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.screens = config.get("screens", ["main"])

    async def setup(self) -> None:
        """Wire encoder for screen cycling."""

        @self.card.on("next_screen")
        async def _next() -> None:
            # Screen navigation is handled at the provisioner level
            pass

        @self.card.on("previous_screen")
        async def _prev() -> None:
            pass

    async def sync_state(self) -> None:
        """Sync dashboard info (time, date, HA connection status)."""
        self.card.set("connected", True)
