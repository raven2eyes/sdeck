"""Provisioner — loads profiles, applies templates, and wires controllers to devices."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from deckui import DuiCard, DuiKey, Screen, load_package
from deckui.dui.schema import ImageBinding
from deckui.runtime.deck import Deck
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
        self._key_syncs: list[tuple[DuiKey, object, object]] = []
        self.active_scene: str = ""

    def add_key_sync(self, key: DuiKey, entity: object, sync_fn: object) -> None:
        """Track a key state sync callback for re-triggering."""
        self._key_syncs.append((key, entity, sync_fn))

    async def sync_keys(self) -> None:
        """Re-trigger all key state sync callbacks."""
        for _key, _entity, sync_fn in self._key_syncs:
            await sync_fn()  # type: ignore[operator]

    async def sync_all(self) -> None:
        """Re-sync all controllers and keys."""
        await self.sync_keys()
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
        self._decks: dict[str, Deck] = {}

    def get_profile(self, serial: str) -> DeviceProfile | None:
        """Resolve the profile for a device by serial, falling back to default."""
        return self.profiles.get(serial) or self.profiles.get(None)

    def get_deck(self, serial: str) -> Deck | None:
        """Return the Deck instance for a serial, if tracked."""
        return self._decks.get(serial)

    def _scene_profiles(self, primary_serial: str) -> list[DeviceProfile]:
        """Return profiles as scenes: primary first, then those listed in scenes field."""
        primary = self.get_profile(primary_serial)
        if primary is None:
            return []

        scenes: list[DeviceProfile] = [primary]
        if not primary.scenes:
            return scenes

        # Build a name→profile lookup from all loaded profiles
        by_name: dict[str, DeviceProfile] = {}
        for prof in self.profiles.values():
            if prof.name:
                by_name[prof.name] = prof

        for scene_name in primary.scenes:
            scene_prof = by_name.get(scene_name)
            if scene_prof is None:
                log.warning("Scene profile '%s' not found, skipping", scene_name)
                continue
            if scene_prof is primary:
                continue
            scenes.append(scene_prof)
        return scenes

    def _build_screen(
        self,
        screen: Screen,
        profile: DeviceProfile,
        provisioned: ProvisionedDeck,
        audio_card: DuiCard | None = None,
    ) -> None:
        """Populate a screen's keys and cards from a profile (sync key loading)."""
        model_dir = _MODEL_DIR[profile.model]

        # Apply key templates
        for key_slot in profile.templates.keys:
            template_path = self.templates_dir / model_dir / key_slot.template
            if not template_path.exists():
                log.warning("Key template not found: %s", template_path)
                continue
            spec = load_package(str(template_path))
            key = DuiKey(spec)
            for binding_name, value in key_slot.config.items():
                # Skip action-related keys — they're not DUI bindings
                if binding_name in ("action", "domain", "entity", "action_data", "actions"):
                    continue
                # Load image files for ImageBinding values
                if (
                    isinstance(value, str)
                    and isinstance(spec.bindings.get(binding_name), ImageBinding)
                ):
                    img_path = Path(value)
                    if not img_path.is_absolute():
                        img_path = Path.cwd() / img_path
                    if img_path.is_file():
                        value = img_path.read_bytes()
                    else:
                        log.warning("Image file not found: %s", img_path)
                        continue
                key.set(binding_name, value)
            screen.set_key(key_slot.slot, key)

            # Wire key press action if configured
            actions = key_slot.config.get("actions")
            action = key_slot.config.get("action")
            domain = key_slot.config.get("domain")
            entity = key_slot.config.get("entity")
            if actions:
                self._wire_key_actions(key, actions)
                # State sync for the first light/switch entity
                for act in actions:
                    if act.get("domain") in ("light", "switch"):
                        self._wire_key_state_sync(
                            key, act["domain"], act["entity"], provisioned
                        )
                        break
            elif action and domain and entity:
                action_data = key_slot.config.get("action_data")
                busy_card = audio_card if str(action) == "play_media" else None
                self._wire_key_action(
                    key, str(action), str(domain), str(entity),
                    action_data=action_data,
                    busy_card=busy_card,
                )
                if str(domain) in ("light", "switch"):
                    self._wire_key_state_sync(key, str(domain), str(entity), provisioned)
                elif str(action) == "select_source" and action_data:
                    self._wire_key_source_sync(
                        key, str(domain), str(entity),
                        action_data.get("source", ""), provisioned,
                    )

    async def _wire_controllers(
        self,
        screen: Screen,
        profile: DeviceProfile,
        provisioned: ProvisionedDeck,
        deck: Deck,
    ) -> DuiCard | None:
        """Load touchscreen cards and wire controllers.

        Returns the AudioCard for this screen (if any) so that key
        handlers can trigger its busy spinner on media switches.
        """
        model_dir = _MODEL_DIR[profile.model]
        audio_card: DuiCard | None = None

        for ts_slot in profile.templates.touchscreen:
            template_path = self.templates_dir / model_dir / ts_slot.template
            if not template_path.exists():
                log.warning("Touchscreen template not found: %s", template_path)
                continue
            spec = load_package(str(template_path))
            card = DuiCard(spec)
            screen.set_card(ts_slot.slot, card)

            if ts_slot.controller:
                ctrl_cls = get_controller(ts_slot.controller)
                config: dict[str, Any] = {**ts_slot.config, "_deck": deck}
                ctrl = ctrl_cls(ha=self.ha, card=card, config=config)
                await ctrl.setup()
                provisioned.controllers.append(ctrl)
                if ts_slot.controller == "audio":
                    audio_card = card

        return audio_card

    async def provision(self, deck: Deck, serial: str) -> ProvisionedDeck | None:
        """Provision a connected Stream Deck with all profiles as switchable scenes."""
        profile = self.get_profile(serial)
        if profile is None:
            log.warning("No profile found for device %s, skipping", serial)
            return None

        log.info("Provisioning device %s with model=%s", serial, profile.model.value)
        provisioned = ProvisionedDeck(serial, profile)

        scenes = self._scene_profiles(serial)
        scene_names = [p.name or f"scene-{i}" for i, p in enumerate(scenes)]

        for i, (scene_name, scene_profile) in enumerate(zip(scene_names, scenes, strict=True)):
            screen = deck.screen(scene_name)
            audio_card = await self._wire_controllers(
                screen, scene_profile, provisioned, deck,
            )
            self._build_screen(screen, scene_profile, provisioned, audio_card)

            # Wire key 0 to cycle to the next scene
            if len(scenes) > 1:
                key0 = screen.key(0)
                if hasattr(key0, "on_event"):
                    next_scene = scene_names[(i + 1) % len(scene_names)]
                    self._wire_scene_cycle(deck, key0, next_scene, serial)  # type: ignore[arg-type]

            log.info("Scene '%s' loaded for device %s", scene_name, serial)

        # Hydrate all entity states from HA REST API, then sync
        await self.ha.state.refresh_all()
        await provisioned.sync_all()

        # Activate the primary scene
        await deck.set_screen(scene_names[0])
        provisioned.active_scene = scene_names[0]

        self.active_decks[serial] = provisioned
        self._decks[serial] = deck
        log.info("Device %s provisioned with %d scene(s)", serial, len(scenes))
        return provisioned

    def _wire_scene_cycle(
        self, deck: Deck, key: DuiKey, next_scene: str, serial: str,
    ) -> None:
        """Wire a key's press event to switch to the next scene."""
        provisioner = self

        @key.on_event("press")
        async def _cycle_scene() -> None:
            log.info("Switching to scene: %s", next_scene)
            await deck.set_screen(next_scene)
            pd = provisioner.active_decks.get(serial)
            if pd:
                pd.active_scene = next_scene

    def _wire_key_action(
        self, key: DuiKey, action: str, domain: str, entity: str,
        action_data: dict[str, Any] | None = None,
        busy_card: DuiCard | None = None,
    ) -> None:
        """Wire a key's press event to a Home Assistant action."""
        ha = self.ha

        @key.on_event("press")
        async def _key_action() -> None:
            try:
                if busy_card is not None:
                    await busy_card.start_busy()
                accessor = getattr(ha, domain)
                obj = accessor(entity)
                method = getattr(obj, action)
                if action_data:
                    if action == "play_media":
                        # Sonos favorite_item_id requires REST (UPnP 800 on WS).
                        await obj._call_service(
                            "play_media", action_data, prefer="rest",
                        )
                    else:
                        await method(**action_data)
                else:
                    await method()
                log.info("Key action: %s.%s.%s()", domain, entity, action)
            except Exception:
                log.exception("Key action failed: %s.%s.%s", domain, entity, action)
                if busy_card is not None:
                    await busy_card.finish_busy()

    def _wire_key_actions(
        self, key: DuiKey, actions: list[dict[str, str]]
    ) -> None:
        """Wire a key's press event to multiple Home Assistant actions."""
        ha = self.ha

        @key.on_event("press")
        async def _key_actions() -> None:
            for act in actions:
                try:
                    accessor = getattr(ha, act["domain"])
                    obj = accessor(act["entity"])
                    method = getattr(obj, act["action"])
                    await method()
                    log.info(
                        "Key action: %s.%s.%s()",
                        act["domain"], act["entity"], act["action"],
                    )
                except Exception:
                    log.exception(
                        "Key action failed: %s.%s.%s",
                        act.get("domain"), act.get("entity"), act.get("action"),
                    )

    def _wire_key_state_sync(
        self, key: DuiKey, domain: str, entity: str, provisioned: ProvisionedDeck
    ) -> None:
        """Subscribe to entity state changes and dim key icon + background."""
        accessor = getattr(self.ha, domain)
        ent = accessor(entity)

        async def _sync_icon(_old: object = None, _new: object = None) -> None:
            is_on = ent.state == "on"
            log.debug(
                "Key sync: %s.%s state=%r is_on=%s", domain, entity, ent.state, is_on
            )
            key.set("icon_color", "#ffffff" if is_on else "#555555")
            key.set("active", "#1a1a2e" if is_on else "#0d0d1a")
            await key.request_refresh()

        ent.on_state_change(_sync_icon)
        provisioned.add_key_sync(key, ent, _sync_icon)

    def _wire_key_source_sync(
        self, key: DuiKey, domain: str, entity: str, source: str,
        provisioned: ProvisionedDeck,
    ) -> None:
        """Subscribe to entity state changes and highlight key when source matches."""
        accessor = getattr(self.ha, domain)
        ent = accessor(entity)

        async def _sync_source(_old: object = None, _new: object = None) -> None:
            is_active = ent.attributes.get("source") == source
            key.set("icon_color", "#ffffff" if is_active else "#555555")
            key.set("active", "#1a1a2e" if is_active else "#0d0d1a")
            await key.request_refresh()

        ent.on_state_change(_sync_source)
        provisioned.add_key_sync(key, ent, _sync_source)

    def remove(self, serial: str) -> None:
        """Remove a provisioned deck (on disconnect)."""
        if serial in self.active_decks:
            del self.active_decks[serial]
            self._decks.pop(serial, None)
            log.info("Device %s removed from active decks", serial)

    async def sync_all_decks(self) -> None:
        """Re-sync all active decks (e.g. after HA reconnect)."""
        for provisioned in self.active_decks.values():
            await provisioned.sync_all()
