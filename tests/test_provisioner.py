"""Tests for provisioner logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from sdeck.profile import DeckModel
from sdeck.provisioner import ProvisionedDeck, Provisioner


@pytest.fixture
def setup_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create profiles and templates directories for testing."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    templates_dir = tmp_path / "templates" / "plus"
    templates_dir.mkdir(parents=True)

    # Create a minimal default profile
    defaults = {
        "model": "stream-deck-plus",
        "templates": {
            "keys": [],
            "touchscreen": [
                {
                    "slot": 0,
                    "template": "AudioCard.dui",
                    "controller": "audio",
                    "config": {"media_player": "test"},
                }
            ],
        },
    }
    (profiles_dir / "defaults.yaml").write_text(yaml.dump(defaults))

    # Create a fake .dui package directory
    audio_dui = templates_dir / "AudioCard.dui"
    audio_dui.mkdir()
    (audio_dui / "manifest.yaml").write_text("name: AudioCard\nversion: '1.0'\n")

    return profiles_dir, templates_dir


def test_provisioner_profile_lookup(setup_dirs: tuple[Path, Path]) -> None:
    profiles_dir, templates_dir = setup_dirs
    ha = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    # Default profile found for unknown serial
    profile = provisioner.get_profile("UNKNOWN_SERIAL")
    assert profile is not None
    assert profile.model == DeckModel.PLUS


def test_provisioner_no_profile_returns_none(tmp_path: Path) -> None:
    """Empty profiles dir → no profile for any serial."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    ha = MagicMock()
    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir,
        ha=ha,
    )
    assert provisioner.get_profile("ANY") is None


async def test_provision_no_profile_returns_none(tmp_path: Path) -> None:
    """Provision returns None when no profile matches."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    ha = MagicMock()
    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir,
        ha=ha,
    )
    deck = MagicMock()
    result = await provisioner.provision(deck, "UNKNOWN")
    assert result is None


@patch("sdeck.provisioner.load_package")
@patch("sdeck.provisioner.DuiCard")
async def test_provision_wires_controllers(
    mock_dui_card: MagicMock,
    mock_load_package: MagicMock,
    setup_dirs: tuple[Path, Path],
) -> None:
    """Provision loads templates and wires controllers."""
    profiles_dir, templates_dir = setup_dirs

    # Mock HA and its domain accessors
    ha = MagicMock()
    ha.state = MagicMock()
    ha.state.refresh_all = AsyncMock()
    player = MagicMock()
    player.volume_up = AsyncMock()
    player.toggle = AsyncMock()
    player.state = MagicMock(state="playing", attributes={"media_title": "", "media_artist": ""})
    player.on_state_change = MagicMock()
    ha.media_player = MagicMock(return_value=player)

    # Mock DuiCard
    card_instance = MagicMock()
    card_instance.on = MagicMock(side_effect=lambda name: lambda fn: fn)
    card_instance.set = MagicMock()
    mock_dui_card.return_value = card_instance

    mock_load_package.return_value = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    # Mock the deck object
    screen = MagicMock()
    screen.set_card = MagicMock()
    deck = MagicMock()
    deck.screen = MagicMock(return_value=screen)
    deck.set_screen = AsyncMock()

    result = await provisioner.provision(deck, "TEST_SERIAL")

    assert result is not None
    assert result.serial == "TEST_SERIAL"
    assert len(result.controllers) == 1
    deck.set_screen.assert_awaited_once_with("defaults")


@patch("sdeck.provisioner.load_package")
@patch("sdeck.provisioner.DuiKey")
async def test_provision_applies_key_templates(
    mock_dui_key: MagicMock,
    mock_load_package: MagicMock,
    tmp_path: Path,
) -> None:
    """Provision applies key templates to the screen."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    templates_dir = tmp_path / "templates" / "plus"
    templates_dir.mkdir(parents=True)

    defaults = {
        "model": "stream-deck-plus",
        "templates": {
            "keys": [{"slot": 0, "template": "IconKey.dui"}],
            "touchscreen": [],
        },
    }
    (profiles_dir / "defaults.yaml").write_text(yaml.dump(defaults))

    # Create key template
    key_dui = templates_dir / "IconKey.dui"
    key_dui.mkdir()
    (key_dui / "manifest.yaml").write_text("name: IconKey\nversion: '1.0'\n")

    ha = MagicMock()
    ha.state = MagicMock()
    ha.state.refresh_all = AsyncMock()
    key_instance = MagicMock()
    mock_dui_key.return_value = key_instance
    mock_load_package.return_value = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    screen = MagicMock()
    deck = MagicMock()
    deck.screen = MagicMock(return_value=screen)
    deck.set_screen = AsyncMock()

    await provisioner.provision(deck, "KEY_TEST")
    screen.set_key.assert_called_once_with(0, key_instance)


async def test_provision_skips_missing_template(
    setup_dirs: tuple[Path, Path],
) -> None:
    """Provision skips templates that don't exist on disk."""
    profiles_dir, templates_dir = setup_dirs

    # Remove the template directory
    import shutil
    audio_dui = templates_dir / "AudioCard.dui"
    shutil.rmtree(audio_dui)

    ha = MagicMock()
    ha.state = MagicMock()
    ha.state.refresh_all = AsyncMock()
    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    screen = MagicMock()
    deck = MagicMock()
    deck.screen = MagicMock(return_value=screen)
    deck.set_screen = AsyncMock()

    result = await provisioner.provision(deck, "MISSING_TEMPLATE")
    assert result is not None
    assert len(result.controllers) == 0


def test_remove_deck(setup_dirs: tuple[Path, Path]) -> None:
    """Remove removes a device from active decks."""
    profiles_dir, templates_dir = setup_dirs
    ha = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    # Manually add a provisioned deck
    profile = provisioner.get_profile("X")
    assert profile is not None
    pd = ProvisionedDeck("SERIAL_1", profile)
    provisioner.active_decks["SERIAL_1"] = pd

    provisioner.remove("SERIAL_1")
    assert "SERIAL_1" not in provisioner.active_decks


def test_remove_unknown_serial_noop(setup_dirs: tuple[Path, Path]) -> None:
    """Remove does nothing for unknown serial."""
    profiles_dir, templates_dir = setup_dirs
    ha = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )
    provisioner.remove("NONEXISTENT")  # should not raise


async def test_sync_all_decks(setup_dirs: tuple[Path, Path]) -> None:
    """sync_all_decks re-syncs all active provisioned decks."""
    profiles_dir, templates_dir = setup_dirs
    ha = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    # Add mock provisioned decks
    mock_ctrl = AsyncMock()
    pd = ProvisionedDeck("S1", provisioner.get_profile("S1"))
    pd.controllers.append(mock_ctrl)
    provisioner.active_decks["S1"] = pd

    await provisioner.sync_all_decks()
    mock_ctrl.sync_state.assert_awaited_once()


@patch("sdeck.provisioner.load_package")
@patch("sdeck.provisioner.DuiCard")
async def test_multi_scene_provision(
    mock_dui_card: MagicMock,
    mock_load_package: MagicMock,
    setup_dirs: tuple[Path, Path],
) -> None:
    """Multiple profiles are provisioned as switchable scenes."""
    profiles_dir, templates_dir = setup_dirs

    # Add device profiles so we get 2 scenes
    devices_dir = profiles_dir / "devices"
    devices_dir.mkdir()
    device_profile = {
        "extends": "defaults",
        "serial": "SCENE_SERIAL",
        "scenes": ["living-room"],
        "templates": {
            "keys": [],
            "touchscreen": [
                {
                    "slot": 0,
                    "template": "AudioCard.dui",
                    "controller": "audio",
                    "config": {"media_player": "bedroom"},
                }
            ],
        },
    }
    (devices_dir / "bedroom-one.yaml").write_text(yaml.dump(device_profile))

    other_profile = {
        "extends": "defaults",
        "serial": "OTHER_SERIAL",
        "templates": {
            "keys": [],
            "touchscreen": [
                {
                    "slot": 0,
                    "template": "AudioCard.dui",
                    "controller": "audio",
                    "config": {"media_player": "living_room"},
                }
            ],
        },
    }
    (devices_dir / "living-room.yaml").write_text(yaml.dump(other_profile))

    ha = MagicMock()
    ha.state = MagicMock()
    ha.state.refresh_all = AsyncMock()
    player = MagicMock()
    player.set_volume = AsyncMock()
    player.play_pause = AsyncMock()
    player.next = AsyncMock()
    player.previous = AsyncMock()
    player.volume_level = 0.5
    player.state = "playing"
    player.attributes = {"media_title": "", "media_artist": ""}
    player.on_state_change = MagicMock()
    ha.media_player = MagicMock(return_value=player)

    card_instance = MagicMock()
    card_instance.on = MagicMock(side_effect=lambda name: lambda fn: fn)
    card_instance.set = MagicMock()
    mock_dui_card.return_value = card_instance
    mock_load_package.return_value = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    # Mock screen that returns a key with on_event
    mock_key = MagicMock()
    mock_key.on_event = MagicMock(side_effect=lambda name: lambda fn: fn)

    screen = MagicMock()
    screen.set_card = MagicMock()
    screen.key = MagicMock(return_value=mock_key)

    deck = MagicMock()
    deck.screen = MagicMock(return_value=screen)
    deck.set_screen = AsyncMock()

    result = await provisioner.provision(deck, "SCENE_SERIAL")

    assert result is not None
    # Two scenes: bedroom (primary) + living-room (from scenes list)
    assert deck.screen.call_count == 2
    screen_names = [c.args[0] for c in deck.screen.call_args_list]
    assert "bedroom-one" in screen_names
    assert "living-room" in screen_names
    # Primary scene activated
    deck.set_screen.assert_awaited_once_with("bedroom-one")
    # Key 0 on_event wired for scene cycling
    mock_key.on_event.assert_called()


@patch("sdeck.provisioner.load_package")
@patch("sdeck.provisioner.DuiKey")
async def test_key_light_state_sync(
    mock_dui_key: MagicMock,
    mock_load_package: MagicMock,
    tmp_path: Path,
) -> None:
    """Light domain keys get icon_color synced to entity state."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    templates_dir = tmp_path / "templates" / "plus"
    templates_dir.mkdir(parents=True)

    defaults = {
        "model": "stream-deck-plus",
        "templates": {
            "keys": [
                {
                    "slot": 1,
                    "template": "IconKey.dui",
                    "config": {
                        "icon": "mdi:lightbulb",
                        "label": "Light",
                        "action": "toggle",
                        "domain": "light",
                        "entity": "test_light",
                    },
                }
            ],
            "touchscreen": [],
        },
    }
    (profiles_dir / "defaults.yaml").write_text(yaml.dump(defaults))

    key_dui = templates_dir / "IconKey.dui"
    key_dui.mkdir()
    (key_dui / "manifest.yaml").write_text("name: IconKey\nversion: '1.0'\n")

    # Mock HA light entity
    light = MagicMock()
    light.state = "on"
    state_callbacks: list = []
    light.on_state_change = MagicMock(side_effect=lambda cb: state_callbacks.append(cb))

    ha = MagicMock()
    ha.light = MagicMock(return_value=light)
    ha.state = MagicMock()
    ha.state.refresh_all = AsyncMock()

    key_instance = MagicMock()
    key_instance.on_event = MagicMock(side_effect=lambda name: lambda fn: fn)
    key_instance.request_refresh = AsyncMock()
    mock_dui_key.return_value = key_instance
    mock_load_package.return_value = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    screen = MagicMock()
    deck = MagicMock()
    deck.screen = MagicMock(return_value=screen)
    deck.set_screen = AsyncMock()

    await provisioner.provision(deck, "LIGHT_TEST")

    # Initial sync: light is "on" → white icon, normal background
    key_instance.set.assert_any_call("icon_color", "#ffffff")
    key_instance.set.assert_any_call("active", "#1a1a2e")

    # Simulate state change to off
    light.state = "off"
    assert len(state_callbacks) > 0
    await state_callbacks[0](None, None)
    key_instance.set.assert_any_call("icon_color", "#555555")
    key_instance.set.assert_any_call("active", "#0d0d1a")


@patch("sdeck.provisioner.load_package")
@patch("sdeck.provisioner.DuiKey")
async def test_multi_action_key(
    mock_dui_key: MagicMock,
    mock_load_package: MagicMock,
    tmp_path: Path,
) -> None:
    """Multi-action key fires all configured HA actions on press."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    templates_dir = tmp_path / "templates" / "plus"
    templates_dir.mkdir(parents=True)

    defaults = {
        "model": "stream-deck-plus",
        "templates": {
            "keys": [
                {
                    "slot": 0,
                    "template": "IconKey.dui",
                    "config": {
                        "icon": "mdi:power-sleep",
                        "label": "Sleep",
                        "actions": [
                            {"action": "off", "domain": "light", "entity": "bedroom"},
                            {"action": "pause", "domain": "media_player", "entity": "bedroom"},
                        ],
                    },
                }
            ],
            "touchscreen": [],
        },
    }
    (profiles_dir / "defaults.yaml").write_text(yaml.dump(defaults))

    key_dui = templates_dir / "IconKey.dui"
    key_dui.mkdir()
    (key_dui / "manifest.yaml").write_text("name: IconKey\nversion: '1.0'\n")

    # Mock HA entities
    light = MagicMock()
    light.state = "on"
    light.off = AsyncMock()
    light.on_state_change = MagicMock()
    player = MagicMock()
    player.pause = AsyncMock()

    ha = MagicMock()
    ha.light = MagicMock(return_value=light)
    ha.media_player = MagicMock(return_value=player)
    ha.state = MagicMock()
    ha.state.refresh_all = AsyncMock()

    # Track the press handler registered on the key
    press_handlers: list = []
    key_instance = MagicMock()
    key_instance.on_event = MagicMock(
        side_effect=lambda name: (lambda fn: press_handlers.append(fn) or fn)
    )
    key_instance.request_refresh = AsyncMock()
    mock_dui_key.return_value = key_instance
    mock_load_package.return_value = MagicMock()

    provisioner = Provisioner(
        profiles_dir=profiles_dir,
        templates_dir=templates_dir.parent,
        ha=ha,
    )

    screen = MagicMock()
    deck = MagicMock()
    deck.screen = MagicMock(return_value=screen)
    deck.set_screen = AsyncMock()

    await provisioner.provision(deck, "SLEEP_TEST")

    # Find the multi-action handler (first handler registered on key press)
    assert len(press_handlers) > 0
    await press_handlers[0]()

    # Both actions should have fired
    light.off.assert_awaited_once()
    player.pause.assert_awaited_once()
