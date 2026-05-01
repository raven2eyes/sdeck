"""Main entrypoint — multi-device orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from deckui import DeckManager, DeviceInfo
from dotenv import load_dotenv
from haclient import HAClient

# Import controllers to trigger registration
import sdeck.controllers.audio  # noqa: F401
import sdeck.controllers.dashboard  # noqa: F401
import sdeck.controllers.light  # noqa: F401
import sdeck.controllers.timer  # noqa: F401
from sdeck.provisioner import Provisioner

load_dotenv()

log = logging.getLogger(__name__)


async def run() -> None:
    """Run the SDeck provisioner."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level, format="%(levelname)s: %(name)s: %(message)s")

    ha_url = os.environ.get("HA_URL", "")
    ha_token = os.environ.get("HA_TOKEN", "")
    if not ha_url or not ha_token:
        log.error("HA_URL and HA_TOKEN must be set in environment or .env")
        return

    profiles_dir = Path(os.environ.get("PROFILES_DIR", "./profiles"))
    templates_dir = Path(os.environ.get("TEMPLATES_DIR", "./templates"))
    serial_filter = os.environ.get("STREAMDECK_SERIAL")

    manager = DeckManager()

    async with HAClient.from_url(ha_url, token=ha_token) as ha:
        provisioner = Provisioner(
            profiles_dir=profiles_dir,
            templates_dir=templates_dir,
            ha=ha,
        )

        @manager.on_connect()
        async def on_connect(deck: object, info: DeviceInfo) -> None:
            serial = info.serial
            if serial_filter and serial != serial_filter:
                log.debug("Ignoring device %s (filter: %s)", serial, serial_filter)
                return

            log.info("Stream Deck connected: %s (model=%s)", serial, info.model)
            await provisioner.provision(deck, serial)

        @manager.on_disconnect
        async def on_disconnect(info: DeviceInfo) -> None:
            log.warning("Stream Deck disconnected: %s", info.serial)
            provisioner.remove(info.serial)

        # Re-sync all decks when HA reconnects
        ha.on_reconnect(provisioner.sync_all_decks)

        log.info("SDeck provisioner starting...")
        if serial_filter:
            log.info("Filtering for device: %s", serial_filter)
        log.info("Profiles: %s", profiles_dir.resolve())
        log.info("Templates: %s", templates_dir.resolve())
        log.info("Loaded %d profile(s)", len(provisioner.profiles))

        async with manager:
            await manager.wait_closed()


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
