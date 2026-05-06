"""Playlist browser controller — browse and play Sonos favorites."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller

log = logging.getLogger(__name__)


@register_controller("playlist")
class PlaylistController(BaseController):
    """Browse Sonos favorites on a touchscreen card using encoder navigation.

    Reuses the AudioCard template:
    - title  → favorite name
    - artist → category (Playlist / Radio / Album)
    - album  → position indicator (e.g. "3 / 16")
    - state  → "Browse"
    - volume → scroll progress bar
    - encoder turn → scroll through favorites
    - encoder press → play selected favorite
    """

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.entity_name = config.get("media_player", "entertainment")
        self._favorites: list[dict[str, str]] = []
        self._index: int = 0

    async def setup(self) -> None:
        """Wire encoder events and load favorites from HA."""
        await self._load_favorites()

        @self.card.on("volume_up")
        async def _next_fav(*_args: Any) -> None:
            if not self._favorites:
                return
            self._index = (self._index + 1) % len(self._favorites)
            self._update_display()

        @self.card.on("volume_down")
        async def _prev_fav(*_args: Any) -> None:
            if not self._favorites:
                return
            self._index = (self._index - 1) % len(self._favorites)
            self._update_display()

        @self.card.on("mute_toggle")
        async def _play_selected(*_args: Any) -> None:
            if not self._favorites:
                return
            fav = self._favorites[self._index]
            await self._play_favorite(fav)

        @self.card.on("toggle_play_pause")
        async def _play_hold(*_args: Any) -> None:
            """Long press also plays the selected item."""
            if not self._favorites:
                return
            fav = self._favorites[self._index]
            await self._play_favorite(fav)

    async def sync_state(self) -> None:
        """Sync the display with current selection."""
        if not self._favorites:
            await self._load_favorites()
        self._update_display()

    async def _load_favorites(self) -> None:
        """Load Sonos favorites from Home Assistant via WebSocket."""
        try:
            ws = self.ha._ws  # noqa: SLF001
            entity_id = f"media_player.{self.entity_name}"

            # Browse favorites root to get categories
            results = await ws.send_command({
                "type": "media_player/browse_media",
                "entity_id": entity_id,
                "media_content_type": "favorites",
                "media_content_id": "",
            })
            categories = results.get("children", [])
            all_favs: list[dict[str, str]] = []

            for cat in categories:
                cat_id = cat.get("media_content_id", "")
                cat_result = await ws.send_command({
                    "type": "media_player/browse_media",
                    "entity_id": entity_id,
                    "media_content_type": "favorites_folder",
                    "media_content_id": cat_id,
                })
                for item in cat_result.get("children", []):
                    all_favs.append({
                        "title": item.get("title", "Unknown"),
                        "content_type": item.get("media_content_type", ""),
                        "content_id": item.get("media_content_id", ""),
                        "category": _friendly_category(cat_id),
                        "thumbnail": item.get("thumbnail", ""),
                    })

            self._favorites = all_favs
            log.info("Loaded %d Sonos favorites for playlist browser", len(all_favs))
        except Exception:
            log.exception("Failed to load Sonos favorites")
            self._favorites = []

    async def _play_favorite(self, fav: dict[str, str]) -> None:
        """Play a favorite item on the media player."""
        try:
            await self.card.start_busy()
            player = self.ha.media_player(self.entity_name)
            await player._call_service(
                "play_media",
                {
                    "media_content_type": fav["content_type"],
                    "media_content_id": fav["content_id"],
                },
                prefer="rest",
            )
            log.info("Playing favorite: %s (%s)", fav["title"], fav["content_id"])
            await self.card.finish_busy()
        except Exception:
            log.exception("Failed to play favorite: %s", fav["title"])
            await self.card.finish_busy()

    def _update_display(self) -> None:
        """Update card bindings with current selection."""
        if not self._favorites:
            self.card.set("title", "No Favorites")
            self.card.set("artist", "")
            self.card.set("album", "")
            self.card.set("state", "Browse")
            self.card.set("volume", 0.0)
            self.card.set("value_text", "0/0")
            return

        fav = self._favorites[self._index]
        self.card.set("title", fav["title"])
        self.card.set("artist", fav["category"])
        self.card.set("album", f"{self._index + 1} / {len(self._favorites)}")
        self.card.set("state", "Browse")
        progress = (self._index + 1) / len(self._favorites)
        self.card.set("volume", progress)
        self.card.set("value_text", f"{self._index + 1}/{len(self._favorites)}")
        asyncio.ensure_future(self.card.request_refresh())


def _friendly_category(cat_id: str) -> str:
    """Map Sonos category URN to a friendly name."""
    if "playlistContainer" in cat_id:
        return "Playlist"
    if "audioBroadcast" in cat_id:
        return "Radio"
    if "musicAlbum" in cat_id:
        return "Album"
    if "musicTrack" in cat_id:
        return "Track"
    return "Favorite"
