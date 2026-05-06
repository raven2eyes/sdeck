"""Audio card controller — media player control via HA."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from deckui import DuiCard, fetch_image
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller

log = logging.getLogger(__name__)


def _tv_icon() -> Image.Image:
    """Generate a simple TV icon as a PIL Image."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # TV body (rounded rectangle)
    draw.rounded_rectangle([20, 40, 180, 150], radius=10, fill="#333333", outline="#dedede", width=3)
    # Screen
    draw.rounded_rectangle([30, 50, 170, 140], radius=6, fill="#1a3d5c")
    # Stand
    draw.rectangle([80, 155, 120, 165], fill="#dedede")
    draw.rectangle([60, 165, 140, 172], fill="#dedede")
    # "TV" text on screen
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((100, 90), "TV", fill="#ffffff", font=font, anchor="mm")
    return img


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
        async def _vol_up(*_args: Any) -> None:
            current = player.volume_level or 0.0
            new_vol = min(1.0, current + 0.05)
            await player.set_volume(new_vol)
            self.card.set("volume", new_vol)
            self.card.set("value_text", f"{int(new_vol * 100)}%")

        @self.card.on("volume_down")
        async def _vol_down(*_args: Any) -> None:
            current = player.volume_level or 0.0
            new_vol = max(0.0, current - 0.05)
            await player.set_volume(new_vol)
            self.card.set("volume", new_vol)
            self.card.set("value_text", f"{int(new_vol * 100)}%")

        @self.card.on("toggle_play_pause")
        async def _toggle(*_args: Any) -> None:
            await player.play_pause()

        @self.card.on("mute_toggle")
        async def _mute(*_args: Any) -> None:
            await player.mute(not player.is_muted)

        @self.card.on("next")
        async def _next(*_args: Any) -> None:
            await player.next()

        @self.card.on("previous")
        async def _prev(*_args: Any) -> None:
            await player.previous()

        # Granular listeners — update only the changed binding
        player.on_volume_change(self._on_volume_change)
        player.on_media_change(self._on_media_change)
        player.on_play(self._on_play_state)
        player.on_pause(self._on_play_state)
        player.on_stop(self._on_play_state)

    async def sync_state(self) -> None:
        """Sync card UI with current media player state."""
        player = self.ha.media_player(self.entity_name)
        raw = player.state or "unavailable"
        state = raw if raw != "unknown" else "idle"
        self.card.set("state", state.capitalize())

        if player.attributes.get("source") == "TV":
            self.card.set("title", "TV")
            self.card.set("artist", "")
            self.card.set("album", "")
            self.card.set("cover", _tv_icon())
        else:
            np = player.now_playing
            self.card.set("title", np.title or "")
            self.card.set("artist", np.artist or "")
            self.card.set("album", np.album or "")
            await self._set_cover_async(np.entity_picture)

        volume = player.volume_level
        if volume is not None:
            self.card.set("volume", volume)
            self.card.set("value_text", f"{int(volume * 100)}%")

    def _on_volume_change(self, _old: Any, vol: float) -> None:
        """Update volume bar and percentage text."""
        self.card.set("volume", vol)
        self.card.set("value_text", f"{int(vol * 100)}%")
        asyncio.ensure_future(self.card.request_refresh())

    def _on_media_change(self, _old: Any, np: Any) -> None:
        """Update card bindings when the playing media changes."""
        asyncio.ensure_future(self._update_media(np))

    async def _update_media(self, np: Any) -> None:
        """Busy-wrap the media update so a spinner shows during cover fetch."""
        player = self.ha.media_player(self.entity_name)
        await self.card.start_busy()
        if player.attributes.get("source") == "TV":
            self.card.set("title", "TV")
            self.card.set("artist", "")
            self.card.set("album", "")
            self.card.set("cover", _tv_icon())
        else:
            self.card.set("title", np.title or "")
            self.card.set("artist", np.artist or "")
            self.card.set("album", np.album or "")
            await self._set_cover_async(np.entity_picture)
        await self.card.finish_busy()
        await self.card.request_refresh()

    def _on_play_state(self, _old: Any = None, _new: Any = None) -> None:
        """Update play state and refresh card."""
        player = self.ha.media_player(self.entity_name)
        raw = player.state or "unavailable"
        state = raw if raw != "unknown" else "idle"
        self.card.set("state", state.capitalize())
        asyncio.ensure_future(self.card.request_refresh())

    async def _set_cover_async(self, url: str | None) -> None:
        """Fetch cover art in an executor so the spinner can animate."""
        if not url:
            return
        try:
            loop = asyncio.get_running_loop()
            img = await loop.run_in_executor(None, fetch_image, url)
            self.card.set("cover", img)
        except Exception:
            log.debug("Failed to fetch cover art: %s", url)
