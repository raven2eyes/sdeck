"""Tests for provisioner logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from sdeck.profile import DeckModel
from sdeck.provisioner import Provisioner


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
