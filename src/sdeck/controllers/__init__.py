"""Base controller interface and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from deckui import DuiCard
from haclient import HAClient


class BaseController(ABC):
    """Base class for Stream Deck card controllers."""

    def __init__(self, ha: HAClient, card: DuiCard, config: dict[str, Any]) -> None:
        self.ha = ha
        self.card = card
        self.config = config

    @abstractmethod
    async def setup(self) -> None:
        """Wire event handlers and HA state listeners."""

    @abstractmethod
    async def sync_state(self) -> None:
        """Re-sync card UI from current HA state."""


# Controller registry — maps controller name to class
_REGISTRY: dict[str, type[BaseController]] = {}


def register_controller(name: str):  # noqa: ANN201
    """Decorator to register a controller class by name."""

    def decorator(cls: type[BaseController]) -> type[BaseController]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_controller(name: str) -> type[BaseController]:
    """Look up a registered controller class by name."""
    if name not in _REGISTRY:
        msg = f"Unknown controller: {name!r}. Available: {list(_REGISTRY.keys())}"
        raise KeyError(msg)
    return _REGISTRY[name]
