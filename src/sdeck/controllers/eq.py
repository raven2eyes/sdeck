"""EQ controller — bass/treble control via Sonos number entities."""

from __future__ import annotations

import logging
import math
from typing import Any

from deckui import DuiCard
from haclient import HAClient, Entity

from sdeck.controllers import BaseController, register_controller

log = logging.getLogger(__name__)

_EQ_STEP = 1  # step per encoder tick


@register_controller("eq")
class EqController(BaseController):
    """Controls bass/treble using the SoundCard .dui template.

    Maps:
      - encoder turn (no press) → bass adjustment
      - encoder press+turn → treble adjustment
    """

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        super().__init__(ha, card, config)
        self.bass_entity_id = f"number.{config.get('bass_entity', 'living_room_bass')}"
        self.treble_entity_id = f"number.{config.get('treble_entity', 'living_room_treble')}"

    def _ensure_entity(self, entity_id: str) -> Entity:
        """Get or create+register an Entity in the state store."""
        entity = self.ha.state.get(entity_id)
        if entity is None:
            entity = Entity(
                entity_id, self.ha.services, self.ha.state, self.ha._factory.clock
            )
            self.ha.state.register(entity)
        return entity

    def _bass(self) -> Entity:
        return self._ensure_entity(self.bass_entity_id)

    def _treble(self) -> Entity:
        return self._ensure_entity(self.treble_entity_id)

    async def setup(self) -> None:
        """Wire encoder events to bass/treble controls."""
        # Register entities and prime their state from HA
        self._ensure_entity(self.bass_entity_id)
        self._ensure_entity(self.treble_entity_id)
        await self.ha.state.refresh_all()

        @self.card.on("bass_up")
        async def _bass_up(steps: int = 1, **_kw: Any) -> None:
            b = self._bass()
            current = self._safe_float(b.state)
            if current is None:
                return
            new_val = min(10, current + _EQ_STEP * steps)
            await b._call_service("set_value", {"value": new_val}, domain="number")

        @self.card.on("bass_down")
        async def _bass_down(steps: int = 1, **_kw: Any) -> None:
            b = self._bass()
            current = self._safe_float(b.state)
            if current is None:
                return
            new_val = max(-10, current - _EQ_STEP * abs(steps))
            await b._call_service("set_value", {"value": new_val}, domain="number")

        @self.card.on("treble_up")
        async def _treble_up(steps: int = 1, **_kw: Any) -> None:
            t = self._treble()
            current = self._safe_float(t.state)
            if current is None:
                return
            new_val = min(10, current + _EQ_STEP * steps)
            await t._call_service("set_value", {"value": new_val}, domain="number")

        @self.card.on("treble_down")
        async def _treble_down(steps: int = 1, **_kw: Any) -> None:
            t = self._treble()
            current = self._safe_float(t.state)
            if current is None:
                return
            new_val = max(-10, current - _EQ_STEP * abs(steps))
            await t._call_service("set_value", {"value": new_val}, domain="number")

        bass = self._bass()
        treble = self._treble()
        bass.on_state_change(self._on_state_change)
        treble.on_state_change(self._on_state_change)

    async def sync_state(self) -> None:
        """Sync card UI with current bass/treble values."""
        bass = self._bass()
        treble = self._treble()

        bass_val = self._safe_float(bass.state)
        treble_val = self._safe_float(treble.state)
        if bass_val is None or treble_val is None:
            return

        # Compute arc positions: dot follows semicircular gauge path
        bass_x, bass_y = self._arc_ratios(bass_val)
        treble_x, treble_y = self._arc_ratios(treble_val)

        self.card.set("bass_value_text", f"{bass_val:+.0f}")
        self.card.set("bass", bass_x)
        self.card.set("bass_y", bass_y)
        self.card.set("treble_value_text", f"{treble_val:+.0f}")
        self.card.set("treble", treble_x)
        self.card.set("treble_y", treble_y)
        self.card.set("sound", True)

    @staticmethod
    def _safe_float(state: object) -> float | None:
        """Parse entity state to float, returning None for unavailable/unknown."""
        try:
            return float(state)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _arc_ratios(value: float) -> tuple[float, float]:
        """Convert EQ value (-10..+10) to x/y slider ratios for arc movement.

        Returns (x_ratio, y_ratio) both in [0..1] that DeckUI interpolates
        between min_pos/max_pos to place the indicator on the semicircular arc.
        """
        t = (value + 10) / 20  # normalise to 0..1
        angle = math.pi * (1 - t)  # π at left, 0 at right
        x_ratio = (1 + math.cos(angle)) / 2
        y_ratio = 1 - math.sin(angle)
        return x_ratio, y_ratio

    async def _on_state_change(
        self, _old: object = None, _new: object = None
    ) -> None:
        await self.sync_state()
        await self.card.request_refresh()
