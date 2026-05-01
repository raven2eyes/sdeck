"""Tests for main module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from sdeck.main import run


@patch.dict("os.environ", {"HA_URL": "", "HA_TOKEN": ""}, clear=False)
async def test_run_exits_without_credentials() -> None:
    """run() exits early when HA_URL/HA_TOKEN are not set."""
    # Should return without raising (just logs an error)
    await run()


@patch.dict(
    "os.environ",
    {"HA_URL": "http://ha.local:8123", "HA_TOKEN": "test-token"},
    clear=False,
)
@patch("sdeck.main.DeckManager")
@patch("sdeck.main.HAClient")
@patch("sdeck.main.Provisioner")
async def test_run_starts_manager(
    mock_provisioner_cls: MagicMock,
    mock_ha_cls: MagicMock,
    mock_manager_cls: MagicMock,
) -> None:
    """run() creates HAClient, Provisioner, and DeckManager."""
    # Setup mock HAClient context manager
    mock_ha = AsyncMock()
    mock_ha.on_reconnect = MagicMock()
    mock_ha_cls.from_url = MagicMock(return_value=mock_ha)
    mock_ha.__aenter__ = AsyncMock(return_value=mock_ha)
    mock_ha.__aexit__ = AsyncMock(return_value=False)

    # Setup mock provisioner
    mock_prov = MagicMock()
    mock_prov.profiles = {"default": MagicMock()}
    mock_prov.sync_all_decks = AsyncMock()
    mock_provisioner_cls.return_value = mock_prov

    # Setup mock DeckManager context manager
    mock_manager = MagicMock()
    mock_manager.on_connect = MagicMock(return_value=lambda fn: fn)
    mock_manager.on_disconnect = lambda fn: fn
    mock_manager.wait_closed = AsyncMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    mock_manager_cls.return_value = mock_manager

    await run()

    mock_ha_cls.from_url.assert_called_once_with(
        "http://ha.local:8123", token="test-token"
    )
    mock_manager.wait_closed.assert_awaited_once()
