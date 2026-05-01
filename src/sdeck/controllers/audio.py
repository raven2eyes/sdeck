"""Audio card controller — media player control via HA."""

from __future__ import annotations

from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller


@register_controller("audio")
class AudioController(BaseController):
    """Controls the AudioCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.entity_name = config.get("media_player", "entertainment")

    async def setup(self) -> None:
        """Wire encoder and touch events to media player controls."""
        player = self.ha.media_player(self.entity_name)

        @self.card.on("volume_up")
        async def _vol_up() -> None:
            await player.volume_up()

        @self.card.on("volume_down")
        async def _vol_down() -> None:
            await player.volume_down()

        @self.card.on("toggle_play_pause")
        async def _toggle() -> None:
            await player.toggle()

        @self.card.on("next_track")
        async def _next() -> None:
            await player.next_track()

        @self.card.on("previous_track")
        async def _prev() -> None:
            await player.previous_track()

        # Listen for state changes
        player.on_state_change(lambda _old, _new: self._on_state_change())

    async def sync_state(self) -> None:
        """Sync card UI with current media player state."""
        player = self.ha.media_player(self.entity_name)
        state = player.state
        self.card.set("state", state.state if state else "unavailable")
        if state and state.attributes:
            attrs = state.attributes
            self.card.set("title", attrs.get("media_title", ""))
            self.card.set("artist", attrs.get("media_artist", ""))
            volume = attrs.get("volume_level")
            if volume is not None:
                self.card.set("volume", int(volume * 100))

    def _on_state_change(self) -> None:
        """Handle state change callback (schedules async sync)."""
        import asyncio

        asyncio.ensure_future(self.sync_state())
