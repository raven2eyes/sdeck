"""Timer card controller — timer control via upstream DeckUI TimerCard."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from deckui import DuiCard
from haclient import HAClient

from sdeck.controllers import BaseController, register_controller

log = logging.getLogger(__name__)

_DURATION_STEP = 30  # seconds per encoder tick
_DURATION_ALT_STEP = 300  # seconds per press-turn tick (5 min)
_TICK_INTERVAL = 1.0  # seconds between live countdown updates

# Visual colours per state
_COLORS: dict[str, tuple[str, str]] = {
    "idle": ("#1c1c1c", "#dedede"),
    "active": ("#0a3d0a", "#00ff00"),
    "paused": ("#3d3d0a", "#ffff00"),
}


def _seconds_to_hms(total: float) -> str:
    """Format seconds as ``HH:MM:SS``."""
    total = max(int(total), 0)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _hms_to_seconds(hms: str) -> int:
    """Parse ``H:MM:SS`` or ``HH:MM:SS`` into total seconds."""
    parts = hms.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


@register_controller("timer")
class TimerController(BaseController):
    """Controls the upstream TimerCard .dui touchscreen card."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.entity_name = config.get("entity", "streamdeck")
        self._set_duration = 30 * 60  # default 30 minutes in seconds
        self._tick_task: asyncio.Task[None] | None = None

    async def setup(self) -> None:
        """Wire encoder events to timer controls."""
        timer = self.ha.timer(self.entity_name)

        @self.card.on("increase_duration")
        async def _inc(steps: int = 1, **_kw: Any) -> None:
            if self._is_idle(timer):
                self._set_duration = max(0, self._set_duration + _DURATION_STEP * abs(steps))
                self.card.set("timer", _seconds_to_hms(self._set_duration))

        @self.card.on("increase_duration_alt")
        async def _inc_alt(steps: int = 1, **_kw: Any) -> None:
            if self._is_idle(timer):
                self._set_duration = max(0, self._set_duration + _DURATION_ALT_STEP * abs(steps))
                self.card.set("timer", _seconds_to_hms(self._set_duration))

        @self.card.on("decrease_duration")
        async def _dec(steps: int = 1, **_kw: Any) -> None:
            if self._is_idle(timer):
                self._set_duration = max(0, self._set_duration - _DURATION_STEP * abs(steps))
                self.card.set("timer", _seconds_to_hms(self._set_duration))

        @self.card.on("decrease_duration_alt")
        async def _dec_alt(steps: int = 1, **_kw: Any) -> None:
            if self._is_idle(timer):
                self._set_duration = max(0, self._set_duration - _DURATION_ALT_STEP * abs(steps))
                self.card.set("timer", _seconds_to_hms(self._set_duration))

        @self.card.on("toggle")
        async def _toggle(*_args: Any) -> None:
            if self._is_idle(timer):
                duration_str = _seconds_to_hms(self._set_duration)
                await timer.start(duration=duration_str)
            elif timer.is_active:
                await timer.pause()
            elif timer.is_paused:
                await timer.start()

        @self.card.on("reset")
        async def _reset(*_args: Any) -> None:
            if timer.is_active or timer.is_paused:
                await timer.cancel()

        timer.on_state_change(self._on_state_change)

    @staticmethod
    def _is_idle(timer: object) -> bool:
        """Return True if the timer is idle or in an unknown/unavailable state."""
        return timer.is_idle or timer.state in (None, "unavailable", "unknown")  # type: ignore[union-attr]

    async def sync_state(self) -> None:
        """Sync card UI with current timer state."""
        timer = self.ha.timer(self.entity_name)
        state = timer.state or "idle"
        bg, fg = _COLORS.get(state, _COLORS["idle"])
        self.card.set("background", bg)
        self.card.set("foreground", fg)

        if state == "idle":
            self.card.set("timer", _seconds_to_hms(self._set_duration))
            self._stop_tick()
        elif state in ("active", "paused"):
            remaining = timer.time_remaining
            if remaining is not None:
                self.card.set("timer", _seconds_to_hms(remaining))
            elif timer.remaining:
                self.card.set("timer", timer.remaining)
            if state == "active":
                self._start_tick()
            else:
                self._stop_tick()

    async def _on_state_change(
        self, _old: object = None, _new: object = None
    ) -> None:
        old_state = _old.get("state") if isinstance(_old, dict) else None
        new_state = _new.get("state") if isinstance(_new, dict) else None

        await self.sync_state()
        await self.card.request_refresh()

        # Flash the Stream Deck backlight when timer finishes
        if old_state == "active" and new_state == "idle":
            asyncio.create_task(self._flash_backlight())

    # -- Live countdown -----------------------------------------------

    def _start_tick(self) -> None:
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(self._tick_loop())

    def _stop_tick(self) -> None:
        if self._tick_task is not None and not self._tick_task.done():
            self._tick_task.cancel()
            self._tick_task = None

    async def _tick_loop(self) -> None:
        """Update the remaining time display every second while active."""
        try:
            timer = self.ha.timer(self.entity_name)
            while timer.is_active:
                remaining = timer.time_remaining
                if remaining is not None:
                    self.card.set("timer", _seconds_to_hms(remaining))
                    await self.card.request_refresh()
                await asyncio.sleep(_TICK_INTERVAL)
        except asyncio.CancelledError:
            pass

    async def _flash_backlight(self) -> None:
        """Flash the Stream Deck backlight 3 times when timer finishes."""
        deck = self.config.get("_deck")
        if deck is None:
            return
        try:
            original = 100
            for _ in range(3):
                await deck.set_brightness(0)
                await asyncio.sleep(0.3)
                await deck.set_brightness(original)
                await asyncio.sleep(0.3)
        except Exception:  # noqa: BLE001
            log.debug("Backlight flash failed", exc_info=True)
