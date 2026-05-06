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
    player.set_volume = AsyncMock()
    player.play_pause = AsyncMock()
    player.mute = AsyncMock()
    player.next = AsyncMock()
    player.previous = AsyncMock()
    player.volume_level = 0.75
    player.state = "playing"
    player.is_muted = False
    player.attributes = {
        "media_title": "Test Song",
        "media_artist": "Test Artist",
        "volume_level": 0.75,
    }
    now_playing = MagicMock()
    now_playing.title = "Test Song"
    now_playing.artist = "Test Artist"
    now_playing.album = "Test Album"
    now_playing.entity_picture = None
    player.now_playing = now_playing
    player.on_state_change = MagicMock()
    player.on_volume_change = MagicMock()
    player.on_media_change = MagicMock()
    player.on_play = MagicMock()
    player.on_pause = MagicMock()
    player.on_stop = MagicMock()
    ha.media_player = MagicMock(return_value=player)

    # light accessor
    light = MagicMock()
    light.toggle = AsyncMock()
    light.set_brightness = AsyncMock()
    light.set_kelvin = AsyncMock()
    light.state = "on"
    light.brightness = 200
    light.kelvin = 3000
    light.min_kelvin = 2000
    light.max_kelvin = 6500
    light.attributes = {"brightness": 200, "color_temp_kelvin": 3000}
    light.on_state_change = MagicMock()
    ha.light = MagicMock(return_value=light)

    # timer accessor
    timer = MagicMock()
    timer.start = AsyncMock()
    timer.pause = AsyncMock()
    timer.cancel = AsyncMock()
    timer.is_idle = True
    timer.is_active = False
    timer.is_paused = False
    timer.state = "idle"
    timer.time_remaining = None
    timer.remaining = None
    timer.on_state_change = MagicMock()
    ha.timer = MagicMock(return_value=timer)

    # sensor accessor
    sensor = MagicMock()
    sensor.state = "22.5"
    sensor.on_state_change = MagicMock()
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
    card.start_busy = AsyncMock()
    card.finish_busy = AsyncMock()
    card.request_refresh = AsyncMock()
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
            "mute_toggle", "next", "previous",
        }
        registered = set(mock_card._handlers.keys())
        assert expected_events == registered

    async def test_volume_up_calls_player(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["volume_up"]()
        mock_ha.media_player("bedroom").set_volume.assert_awaited_once_with(0.8)
        mock_card.set.assert_any_call("volume", 0.8)
        mock_card.set.assert_any_call("value_text", "80%")

    async def test_volume_down_calls_player(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["volume_down"]()
        mock_ha.media_player("bedroom").set_volume.assert_awaited_once_with(0.7)
        mock_card.set.assert_any_call("volume", 0.7)
        mock_card.set.assert_any_call("value_text", "70%")

    async def test_toggle_play_pause(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["toggle_play_pause"]()
        mock_ha.media_player("bedroom").play_pause.assert_awaited_once()

    async def test_mute_toggle(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["mute_toggle"]()
        mock_ha.media_player("bedroom").mute.assert_awaited_once_with(True)

    async def test_next(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["next"]()
        mock_ha.media_player("bedroom").next.assert_awaited_once()

    async def test_previous(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        await mock_card._handlers["previous"]()
        mock_ha.media_player("bedroom").previous.assert_awaited_once()

    async def test_sync_state_with_media(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("state", "Playing")
        mock_card.set.assert_any_call("title", "Test Song")
        mock_card.set.assert_any_call("artist", "Test Artist")
        mock_card.set.assert_any_call("album", "Test Album")
        mock_card.set.assert_any_call("volume", 0.75)
        mock_card.set.assert_any_call("value_text", "75%")

    async def test_sync_state_unavailable(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.media_player.return_value.state = None
        np = MagicMock()
        np.title = None
        np.artist = None
        np.album = None
        np.entity_picture = None
        mock_ha.media_player.return_value.now_playing = np
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("state", "Unavailable")

    async def test_sync_state_no_volume(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.media_player.return_value.volume_level = None
        np = MagicMock()
        np.title = "Song"
        np.artist = "Artist"
        np.album = ""
        np.entity_picture = None
        mock_ha.media_player.return_value.now_playing = np
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.sync_state()

        # volume set should NOT be called
        calls = [c for c in mock_card.set.call_args_list if c[0][0] == "volume"]
        assert len(calls) == 0

    async def test_default_entity_name(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = AudioController(mock_ha, mock_card, {})
        assert ctrl.entity_name == "entertainment"

    async def test_granular_listeners_registered(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        await ctrl.setup()
        player = mock_ha.media_player("bedroom")
        player.on_volume_change.assert_called_once()
        player.on_media_change.assert_called_once()
        player.on_play.assert_called_once()
        player.on_pause.assert_called_once()
        player.on_stop.assert_called_once()

    async def test_sync_state_with_cover(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        np = MagicMock()
        np.title = "Song"
        np.artist = "Artist"
        np.album = "Album"
        np.entity_picture = "http://hass.local/api/image/album.jpg"
        mock_ha.media_player.return_value.now_playing = np
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        with patch("sdeck.controllers.audio.fetch_image") as mock_fetch:
            mock_img = MagicMock()
            mock_fetch.return_value = mock_img
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_img)
                await ctrl.sync_state()
            mock_card.set.assert_any_call("cover", mock_img)

    async def test_on_media_change_updates_card(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        np = MagicMock()
        np.title = "New Song"
        np.artist = "New Artist"
        np.album = "New Album"
        np.entity_picture = "http://hass.local/art.jpg"
        with patch("sdeck.controllers.audio.fetch_image") as mock_fetch:
            mock_img = MagicMock()
            mock_fetch.return_value = mock_img
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_img)
                await ctrl._update_media(np)
            mock_card.set.assert_any_call("title", "New Song")
            mock_card.set.assert_any_call("artist", "New Artist")
            mock_card.set.assert_any_call("album", "New Album")
            mock_card.set.assert_any_call("cover", mock_img)

    def test_on_volume_change_updates_card(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = AudioController(mock_ha, mock_card, {"media_player": "bedroom"})
        ctrl._on_volume_change(None, 0.6)
        mock_card.set.assert_any_call("volume", 0.6)
        mock_card.set.assert_any_call("value_text", "60%")


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
        expected = {"brightness_up", "brightness_down", "toggle", "kelvin_up", "kelvin_down"}
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

    async def test_brightness_down_negative_steps(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        # DialAccumulator passes negative steps for left turns
        await mock_card._handlers["brightness_down"](steps=-2)
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(150)  # 200 - 25*2

    async def test_brightness_up_caps_at_255(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.brightness = 250
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_up"]()
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(255)

    async def test_brightness_down_floors_at_0(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.brightness = 10
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_down"]()
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(0)

    async def test_brightness_up_with_accumulate_steps(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["brightness_up"](steps=3)
        mock_ha.light("kitchen").set_brightness.assert_awaited_once_with(255)  # 200+75 capped

    async def test_kelvin_up(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["kelvin_up"]()
        mock_ha.light("kitchen").set_kelvin.assert_awaited_once_with(3250)  # 3000 + 250

    async def test_kelvin_down(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["kelvin_down"]()
        mock_ha.light("kitchen").set_kelvin.assert_awaited_once_with(2750)  # 3000 - 250

    async def test_kelvin_down_negative_steps(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["kelvin_down"](steps=-1)
        mock_ha.light("kitchen").set_kelvin.assert_awaited_once_with(2750)  # abs(-1) → 3000-250

    async def test_kelvin_up_caps_at_max(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.kelvin = 6400
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["kelvin_up"]()
        mock_ha.light("kitchen").set_kelvin.assert_awaited_once_with(6500)

    async def test_kelvin_down_floors_at_min(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.kelvin = 2100
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.setup()
        await mock_card._handlers["kelvin_down"]()
        mock_ha.light("kitchen").set_kelvin.assert_awaited_once_with(2000)

    async def test_sync_state(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("lights", True)
        brightness_calls = [
            c for c in mock_card.set.call_args_list if c[0][0] == "brightness"
        ]
        assert len(brightness_calls) == 1
        assert abs(brightness_calls[0][0][1] - 200 / 255) < 0.01
        mock_card.set.assert_any_call("brightness_value_text", "78%")
        mock_card.set.assert_any_call("kelvin_value_text", "3000K")

    async def test_sync_state_off(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.light.return_value.state = "off"
        mock_ha.light.return_value.brightness = 0
        mock_ha.light.return_value.kelvin = None
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl.sync_state()
        mock_card.set.assert_any_call("lights", False)
        mock_card.set.assert_any_call("brightness_value_text", "0%")
        mock_card.set.assert_any_call("kelvin_value_text", "")

    async def test_default_entity_name(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = LightController(mock_ha, mock_card, {})
        assert ctrl.entity_name == "upstairs"

    async def test_on_state_change(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = LightController(mock_ha, mock_card, {"entity": "kitchen"})
        await ctrl._on_state_change()
        # Should call sync_state which sets lights binding
        mock_card.set.assert_any_call("lights", True)


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
        expected = {
            "increase_duration", "increase_duration_alt",
            "decrease_duration", "decrease_duration_alt",
            "toggle", "reset",
        }
        assert set(mock_card._handlers.keys()) == expected

    async def test_toggle_starts_when_idle(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["toggle"]()
        mock_ha.timer("pomodoro").start.assert_awaited_once_with(duration="00:30:00")

    async def test_toggle_pauses_when_active(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.timer.return_value.is_idle = False
        mock_ha.timer.return_value.is_active = True
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["toggle"]()
        mock_ha.timer("pomodoro").pause.assert_awaited_once()

    async def test_toggle_resumes_when_paused(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.timer.return_value.is_idle = False
        mock_ha.timer.return_value.is_active = False
        mock_ha.timer.return_value.is_paused = True
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["toggle"]()
        mock_ha.timer("pomodoro").start.assert_awaited_once()

    async def test_reset_cancels_timer(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.timer.return_value.is_idle = False
        mock_ha.timer.return_value.is_active = True
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["reset"]()
        mock_ha.timer("pomodoro").cancel.assert_awaited_once()

    async def test_increase_duration(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["increase_duration"]()
        mock_card.set.assert_any_call("timer", "00:30:30")  # 30m + 30s

    async def test_decrease_duration(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["decrease_duration"]()
        mock_card.set.assert_any_call("timer", "00:29:30")  # 30m - 30s

    async def test_decrease_duration_negative_steps(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["decrease_duration"](steps=-2)
        mock_card.set.assert_any_call("timer", "00:29:00")  # 30m - 30*2

    async def test_increase_duration_alt(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.setup()
        await mock_card._handlers["increase_duration_alt"]()
        mock_card.set.assert_any_call("timer", "00:35:00")  # 30m + 5m

    async def test_sync_state_idle(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("background", "#1c1c1c")
        mock_card.set.assert_any_call("foreground", "#dedede")
        mock_card.set.assert_any_call("timer", "00:30:00")

    async def test_sync_state_active(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_ha.timer.return_value.state = "active"
        mock_ha.timer.return_value.is_idle = False
        mock_ha.timer.return_value.is_active = True
        mock_ha.timer.return_value.time_remaining = 120.0
        ctrl = TimerController(mock_ha, mock_card, {"entity": "pomodoro"})
        await ctrl.sync_state()

        mock_card.set.assert_any_call("background", "#0a3d0a")
        mock_card.set.assert_any_call("foreground", "#00ff00")
        mock_card.set.assert_any_call("timer", "00:02:00")

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

        expected = {"brightness_up", "brightness_down", "next_screen"}
        assert set(mock_card._handlers.keys()) == expected

    async def test_brightness_up(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        await ctrl.setup()
        await mock_card._handlers["brightness_up"]()
        mock_card.set.assert_any_call("deck_brightness", pytest.approx(0.55, abs=0.01))

    async def test_brightness_down(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        await ctrl.setup()
        await mock_card._handlers["brightness_down"]()
        mock_card.set.assert_any_call("deck_brightness", pytest.approx(0.45, abs=0.01))

    async def test_brightness_down_negative_steps(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        await ctrl.setup()
        await mock_card._handlers["brightness_down"](steps=-2)
        mock_card.set.assert_any_call("deck_brightness", pytest.approx(0.40, abs=0.01))

    async def test_brightness_sets_deck_hardware(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        mock_deck = MagicMock()
        mock_deck.brightness = 50
        mock_deck.set_brightness = AsyncMock()
        ctrl = DashboardController(mock_ha, mock_card, {"_deck": mock_deck})
        await ctrl.setup()
        await mock_card._handlers["brightness_up"]()
        mock_deck.set_brightness.assert_awaited()
        # 0.5 + 0.05 = 0.55 → 55%
        mock_deck.set_brightness.assert_awaited_with(55)

    async def test_sync_state_sets_time_and_date(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        await ctrl.sync_state()
        # Should have set time and date (exact values depend on now)
        time_calls = [c for c in mock_card.set.call_args_list if c[0][0] == "time"]
        date_calls = [c for c in mock_card.set.call_args_list if c[0][0] == "date"]
        assert len(time_calls) == 1
        assert len(date_calls) == 1

    async def test_sync_state_with_sensors(
        self, mock_ha: MagicMock, mock_card: MagicMock
    ) -> None:
        ctrl = DashboardController(
            mock_ha, mock_card,
            {"temperature_entity": "outdoor_temp", "humidity_entity": "outdoor_humidity"},
        )
        # Configure separate sensor returns
        temp_sensor = MagicMock()
        temp_sensor.state = "22.5"
        temp_sensor.on_state_change = MagicMock()
        humid_sensor = MagicMock()
        humid_sensor.state = "45"
        humid_sensor.on_state_change = MagicMock()
        mock_ha.sensor = MagicMock(side_effect=lambda name: {
            "outdoor_temp": temp_sensor,
            "outdoor_humidity": humid_sensor,
        }[name])

        await ctrl.setup()
        await ctrl.sync_state()
        mock_card.set.assert_any_call("temperature", "22.5°C")
        mock_card.set.assert_any_call("humidity", "45%")

    async def test_default_screens(self, mock_ha: MagicMock, mock_card: MagicMock) -> None:
        ctrl = DashboardController(mock_ha, mock_card, {})
        assert ctrl.screens == ["main"]
