"""Provisioner — loads profiles, applies templates, and wires controllers to devices."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from deckui import DuiCard, DuiKey, Screen, load_package
from haclient import HAClient

from sdeck.controllers import BaseController, get_controller
from sdeck.profile import DeckModel, DeviceProfile, load_all_profiles

log = logging.getLogger(__name__)

# Map DeckModel to template subdirectory name
_MODEL_DIR: dict[DeckModel, str] = {
    DeckModel.PLUS: "plus",
    DeckModel.MINI: "mini",
    DeckModel.NEO: "neo",
    DeckModel.XL: "xl",
}


class ProvisionedDeck:
    """A fully provisioned Stream Deck with active controllers."""

    def __init__(self, serial: str, profile: DeviceProfile) -> None:
        self.serial = serial
        self.profile = profile
        self.controllers: list[BaseController] = []

    async def sync_all(self) -> None:
        """Re-sync all controllers (e.g. after HA reconnect)."""
        for ctrl in self.controllers:
            await ctrl.sync_state()


class Provisioner:
    """Reads profiles and provisions Stream Deck devices."""

    def __init__(
        self,
        profiles_dir: Path,
        templates_dir: Path,
        ha: HAClient,
    ) -> None:
        self.profiles_dir = profiles_dir
        self.templates_dir = templates_dir
        self.ha = ha
        self.profiles = load_all_profiles(profiles_dir)
        self.active_decks: dict[str, ProvisionedDeck] = {}

    def get_profile(self, serial: str) -> DeviceProfile | None:
        """Resolve the profile for a device by serial, falling back to default."""
        return self.profiles.get(serial) or self.profiles.get(None)

    async def provision(self, deck: Any, serial: str) -> ProvisionedDeck | None:
        """Provision a connected Stream Deck with its assigned profile."""
        profile = self.get_profile(serial)
        if profile is None:
            log.warning("No profile found for device %s, skipping", serial)
            return None

        log.info("Provisioning device %s with model=%s", serial, profile.model.value)
        provisioned = ProvisionedDeck(serial, profile)

        # Create the main screen
        screen: Screen = deck.screen("main")
        model_dir = _MODEL_DIR[profile.model]

        # Apply key templates
        for key_slot in profile.templates.keys:
            template_path = self.templates_dir / model_dir / key_slot.template
            if not template_path.exists():
                log.warning("Key template not found: %s", template_path)
                continue
            spec = load_package(str(template_path))
            key = DuiKey(spec)
            screen.key(key_slot.slot).set_dui(key)

        # Apply touchscreen card templates with controllers
        for ts_slot in profile.templates.touchscreen:
            template_path = self.templates_dir / model_dir / ts_slot.template
            if not template_path.exists():
                log.warning("Touchscreen template not found: %s", template_path)
                continue
            spec = load_package(str(template_path))
            card = DuiCard(spec)
            screen.touchscreen(ts_slot.slot).set_card(card)

            # Wire controller if specified
            if ts_slot.controller:
                ctrl_cls = get_controller(ts_slot.controller)
                ctrl = ctrl_cls(ha=self.ha, card=card, config=ts_slot.config)
                await ctrl.setup()
                provisioned.controllers.append(ctrl)

        # Sync initial state
        await provisioned.sync_all()

        # Activate screen
        await deck.set_screen("main")

        self.active_decks[serial] = provisioned
        log.info("Device %s provisioned successfully", serial)
        return provisioned

    def remove(self, serial: str) -> None:
        """Remove a provisioned deck (on disconnect)."""
        if serial in self.active_decks:
            del self.active_decks[serial]
            log.info("Device %s removed from active decks", serial)

    async def sync_all_decks(self) -> None:
        """Re-sync all active decks (e.g. after HA reconnect)."""
        for provisioned in self.active_decks.values():
            await provisioned.sync_all()
