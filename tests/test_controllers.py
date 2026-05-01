"""Tests for all controllers — audio, light, timer, dashboard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sdeck.controllers import get_controller, register_controller
from sdeck.controllers.audio import AudioController
from sdeck.controllers.dashboard import DashboardController
from sdeck.controllers.light import LightController
from sdeck.controllers.timer import TimerController

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ha() -> MagicMock:
    """Create a mock HAClient with domain accessors."""
    ha = MagicMock()

    # media_player accessor
    player = MagicMock()
    player.volume_up = AsyncMock()
    player.volume_down = AsyncMock()
    player.toggle = AsyncMock()
    player.next_track = AsyncMock()
    player.previous_track = AsyncMock()
    player.state = MagicMock(
        state="playing",
        attributes={
            "media_title": "Test Song",
            "media_artist": "Test Artist",
            "volume_level": 0.75,
        },
    )
    player.on_state_change = MagicMock()
    ha.media_player = MagicMock(return_value=player)

    # light accessor
    light = MagicMock()
    light.toggle = AsyncMock()
    light.set_brightness = AsyncMock()
    light.state = MagicMock(
        state="on",
        attributes={"brightness": 200, "color_temp": 300},
    )
    light.on_state_change = MagicMock()
    ha.light = MagicMock(return_value=light)

    # timer accessor
    timer = MagicMock()
    timer.start = AsyncMock()
    timer.pause = AsyncMock()
    timer.cancel = AsyncMock()
    ha.timer = MagicMock(return_value=timer)

    # sensor accessor (used by timer sync_state)
    sensor = MagicMock()
    sensor.state = MagicMock(
        state="active",
        attributes={"remaining": "00:05:00"},
    )
    ha.sensor = MagicMock(return_value=sensor)

    return ha


@pytest.fixture
def mock_card() -> MagicMock:
    """Create a mock DuiCard with event registration."""
    card = MagicMock()
    # card.on() returns a decorator — store registered handlers for testing
    card._handlers: dict[str, object] = {}

    def on_factory(event_name: str):  # noqa: ANN202
        def decorator(fn: object) -> object:
            card._handlers[event_name] = fn
            return fn
        return decorator

    card.on = MagicMock(side_effect=on_factory)
    card.set = MagicMock()
    return card


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_registered_controllers(self) -> None:
        assert get_controller("audio") is AudioController
        assert get_controller("light") is LightController
        assert get_controller("timer") is TimerController
        assert get_controller("dashboard") is DashboardController

    def test_get_unknown_controller_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown controller"):
            get_controller("nonexistent")

    def test_register_controller_decorator(self) -> None:
        @register_controller("test_dummy")
        class DummyController(AudioController):
            pass

        assert get_controller("test_dummy") is DummyController


# ---------------------------------------------------------------------------
# AudioController Tests
# ---------------------------------------------------------------------------


class TestAudioController:
    async def test_setup_registers_events(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()

        mock_ha.media_player.assert_called_with("bedroom")
        expected_events = {
            "volume_up", "volume_down", "toggle_play_pause",
            "next_track", "previous_track",
        }
        registered = set(mock_card._handlers.keys())
        assert expected_events == registered

    async def test_volume_up_calls_player(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["volume_up"]()
        mock_ha.media_player("bedroom").volume_up.assert_awaited_once()

    async def test_volume_down_calls_player(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["volume_down"]()
        mock_ha.media_player("bedroom").volume_down.assert_awaited_once()

    async def test_toggle_play_pause(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["toggle_play_pause"]()
        mock_ha.media_player("bedroom").toggle.assert_awaited_once()

    async def test_next_track(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["next_track"]()
        mock_ha.media_player("bedroom").next_track.assert_awaited_once()

    async def test_previous_track(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["previous_track"]()
        mock_ha.media_player("bedroom").previous_track.assert_awaited_once()

    async def test_sync_state_with_media(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("state", "playing")
        mock_card.set.assert_any_call("title", "Test Song")
        mock_card.set.assert_any_call("artist", "Test Artist")
        mock_card.set.assert_any_call("volume", 75)

    async def test_sync_state_unavailable(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.media_player.return_value.state = None
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.sync_state()

        mock_card.set.assert_called_once_with("state", "unavailable")

    async def test_sync_state_no_volume(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.media_player.return_value.state.attributes = {
            "media_title": "Song",
            "media_artist": "Artist",
        }
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.sync_state()

        # volume set should NOT be called
        calls = [c for c in mock_card.set.call_args_list if c[0][0] == "volume"]
        assert len(calls) == 0

    async def test_default_entity_name(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = AudioController(mock_ha, mock_card, {})
        assert ctrl.entity_name == "entertainment"

    def test_on_state_change_schedules_sync(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        with patch("asyncio.ensure_future") as mock_ef:
            ctrl._on_state_change()
            mock_ef.assert_called_once()


# ---------------------------------------------------------------------------
# LightController Tests
# ---------------------------------------------------------------------------


class TestLightController:
    async def test_setup_registers_events(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()

        mock_ha.light.assert_called_with("kitchen")
        expected = {"brightness_up", "brightness_down", "toggle"}
        assert set(mock_card._handlers.keys()) == expected

    async def test_toggle_light(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["toggle"]()
        mock_ha.light("kitchen").toggle.assert_awaited_once()

    async def test_brightness_up(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_up"]()
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(225)  # 200 + 25

    async def test_brightness_down(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_down"]()
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(175)  # 200 - 25

    async def test_brightness_up_caps_at_255(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.state.attributes = {"brightness": 250}
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_up"]()
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(255)

    async def test_brightness_down_floors_at_0(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.state.attributes = {"brightness": 10}
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_down"]()
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(0)

    async def test_brightness_noop_when_no_state(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.state = None
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        # Should not raise
        await mock_card._handlers["brightness_up"]()
        mock_ha.light("kitchen").set_brightness.assert_not_awaited()

    async def test_sync_state(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("state", "on")
        mock_card.set.assert_any_call("brightness", 78)  # 200/255*100 = 78
        mock_card.set.assert_any_call("color_temp", 300)

    async def test_sync_state_unavailable(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.state = None
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.sync_state()
        mock_card.set.assert_called_once_with("state", "unavailable")

    async def test_sync_state_no_color_temp(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.state.attributes = {"brightness": 128}
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.sync_state()
        calls = [c for c in mock_card.set.call_args_list if c[0][0] == "color_temp"]
        assert len(calls) == 0

    async def test_default_entity_name(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = LightController(mock_ha, mock_card, {})
        assert ctrl.entity_name == "upstairs"

    def test_on_state_change(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        with patch("asyncio.ensure_future") as mock_ef:
            ctrl._on_state_change()
            mock_ef.assert_called_once()


# ---------------------------------------------------------------------------
# TimerController Tests
# ---------------------------------------------------------------------------


class TestTimerController:
    async def test_setup_registers_events(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()

        mock_ha.timer.assert_called_with("pomodoro")
        expected = {"start", "pause", "cancel", "adjust"}
        assert set(mock_card._handlers.keys()) == expected

    async def test_start_timer(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["start"]()
        mock_ha.timer("pomodoro").start.assert_awaited_once()

    async def test_pause_timer(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["pause"]()
        mock_ha.timer("pomodoro").pause.assert_awaited_once()

    async def test_cancel_timer(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["cancel"]()
        mock_ha.timer("pomodoro").cancel.assert_awaited_once()

    async def test_sync_state(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("state", "active")
        mock_card.set.assert_any_call("remaining", "00:05:00")

    async def test_sync_state_no_state(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.sensor.return_value.state = None
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.sync_state()
        mock_card.set.assert_called_once_with("state", "idle")

    async def test_sync_state_no_remaining(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.sensor.return_value.state.attributes = {}
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.sync_state()
        calls = [c for c in mock_card.set.call_args_list if c[0][0] == "remaining"]
        assert len(calls) == 0

    async def test_default_entity_name(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = TimerController(mock_ha, mock_card, {})
        assert ctrl.entity_name == "streamdeck"


# ---------------------------------------------------------------------------
# DashboardController Tests
# ---------------------------------------------------------------------------


class TestDashboardController:
    async def test_setup_registers_events(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {"screens": ["main", "media"]})
        await ctrl.setup()

        expected = {"next_screen", "previous_screen"}
        assert set(mock_card._handlers.keys()) == expected

    async def test_sync_state(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        await ctrl.sync_state()
        mock_card.set.assert_called_once_with("connected", True)

    async def test_default_screens(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        assert ctrl.screens == ["main"]
