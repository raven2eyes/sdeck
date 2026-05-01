"""Tests for profile loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sdeck.profile import (
    DeckModel,
    DeviceProfile,
    TemplateSlot,
    load_all_profiles,
    load_profile,
)


@pytest.fixture
def profiles_dir(tmp_path: Path) -> Path:
    """Create a temporary profiles directory with test data."""
    defaults = {
        "model": "stream-deck-plus",
        "templates": {
            "keys": [{"slot": 0, "template": "IconKey.dui"}],
            "touchscreen": [
                {
                    "slot": 0,
                    "template": "AudioCard.dui",
                    "controller": "audio",
                    "config": {"media_player": "entertainment"},
                }
            ],
        },
    }
    (tmp_path / "defaults.yaml").write_text(yaml.dump(defaults))

    devices_dir = tmp_path / "devices"
    devices_dir.mkdir()

    device = {
        "extends": "defaults",
        "serial": "ABC123",
        "templates": {
            "touchscreen": [
                {
                    "slot": 0,
                    "template": "AudioCard.dui",
                    "controller": "audio",
                    "config": {"media_player": "bedroom_speaker"},
                }
            ],
        },
    }
    (devices_dir / "bedroom.yaml").write_text(yaml.dump(device))

    return tmp_path


def test_load_defaults(profiles_dir: Path) -> None:
    profile = load_profile(profiles_dir / "defaults.yaml", profiles_dir)
    assert profile.model == DeckModel.PLUS
    assert len(profile.templates.keys) == 1
    assert profile.templates.keys[0].slot == 0
    assert profile.templates.keys[0].template == "IconKey.dui"


def test_load_device_with_extends(profiles_dir: Path) -> None:
    profile = load_profile(profiles_dir / "devices" / "bedroom.yaml", profiles_dir)
    assert profile.serial == "ABC123"
    assert profile.model == DeckModel.PLUS  # inherited from defaults
    # Touchscreen is overridden (not merged at slot level)
    assert len(profile.templates.touchscreen) == 1
    assert profile.templates.touchscreen[0].config["media_player"] == "bedroom_speaker"


def test_load_all_profiles(profiles_dir: Path) -> None:
    profiles = load_all_profiles(profiles_dir)
    assert None in profiles  # default profile
    assert "ABC123" in profiles  # device profile


def test_invalid_model_raises() -> None:
    with pytest.raises(ValueError):
        DeviceProfile.model_validate({"model": "invalid-model"})


def test_missing_parent_raises(tmp_path: Path) -> None:
    child = {"extends": "nonexistent", "serial": "XYZ"}
    (tmp_path / "child.yaml").write_text(yaml.dump(child))
    with pytest.raises(FileNotFoundError):
        load_profile(tmp_path / "child.yaml", tmp_path)


def test_template_slot_defaults() -> None:
    slot = TemplateSlot(slot=0, template="Test.dui")
    assert slot.controller is None
    assert slot.config == {}
