"""Pydantic models for device provisioning profiles."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DeckModel(StrEnum):
    """Supported Stream Deck models."""

    PLUS = "stream-deck-plus"
    MINI = "stream-deck-mini"
    NEO = "stream-deck-neo"
    XL = "stream-deck-xl"


class TemplateSlot(BaseModel):
    """A single slot assignment in a device profile."""

    slot: int
    template: str
    controller: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class TemplateSet(BaseModel):
    """Complete template assignment for a device."""

    keys: list[TemplateSlot] = Field(default_factory=list)
    touchscreen: list[TemplateSlot] = Field(default_factory=list)


class HAConfig(BaseModel):
    """Home Assistant connection configuration."""

    url: str = ""
    token: str = ""


class DeviceProfile(BaseModel):
    """A provisioning profile for a Stream Deck device."""

    extends: str | None = None
    serial: str | None = None
    model: DeckModel = DeckModel.PLUS
    templates: TemplateSet = Field(default_factory=TemplateSet)
    ha: HAConfig = Field(default_factory=HAConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_profile(path: Path, profiles_dir: Path) -> DeviceProfile:
    """Load a device profile from YAML, resolving `extends` inheritance."""
    raw = yaml.safe_load(path.read_text())
    if raw is None:
        raw = {}

    extends = raw.get("extends")
    if extends:
        parent_path = profiles_dir / f"{extends}.yaml"
        if not parent_path.exists():
            msg = f"Parent profile '{extends}' not found at {parent_path}"
            raise FileNotFoundError(msg)
        parent_raw = yaml.safe_load(parent_path.read_text()) or {}
        # Remove extends from parent to prevent infinite recursion
        parent_raw.pop("extends", None)
        raw = _deep_merge(parent_raw, raw)
        raw.pop("extends", None)

    return DeviceProfile.model_validate(raw)


def load_all_profiles(profiles_dir: Path) -> dict[str | None, DeviceProfile]:
    """Load all device profiles from a directory.

    Returns a mapping of serial number (or None for default) to DeviceProfile.
    """
    profiles: dict[str | None, DeviceProfile] = {}

    # Load defaults first
    defaults_path = profiles_dir / "defaults.yaml"
    if defaults_path.exists():
        profiles[None] = load_profile(defaults_path, profiles_dir)

    # Load per-device profiles
    devices_dir = profiles_dir / "devices"
    if devices_dir.exists():
        for device_file in sorted(devices_dir.glob("*.yaml")):
            profile = load_profile(device_file, profiles_dir)
            if profile.serial:
                profiles[profile.serial] = profile

    return profiles
