"""REST API for SDeck — scene switching and profile queries."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from sdeck.provisioner import Provisioner

log = logging.getLogger(__name__)


def create_app(provisioner: Provisioner) -> web.Application:
    """Create the aiohttp web application with SDeck API routes."""
    app = web.Application()
    app["provisioner"] = provisioner

    app.router.add_get("/api/decks", handle_list_decks)
    app.router.add_get("/api/decks/{serial}/scenes", handle_list_scenes)
    app.router.add_post("/api/decks/{serial}/scene", handle_switch_scene)

    return app


async def handle_list_decks(request: web.Request) -> web.Response:
    """List all connected Stream Deck devices with their active scene."""
    provisioner: Provisioner = request.app["provisioner"]
    decks = []
    for serial, pd in provisioner.active_decks.items():
        profile = pd.profile
        scenes = provisioner._scene_profiles(serial)
        scene_names = [p.name or f"scene-{i}" for i, p in enumerate(scenes)]
        decks.append({
            "serial": serial,
            "name": profile.name,
            "model": profile.model.value,
            "scenes": scene_names,
            "active_scene": pd.active_scene if hasattr(pd, "active_scene") else scene_names[0],
        })
    return web.json_response(decks)


async def handle_list_scenes(request: web.Request) -> web.Response:
    """List available scenes for a specific device."""
    provisioner: Provisioner = request.app["provisioner"]
    serial = request.match_info["serial"]

    pd = provisioner.active_decks.get(serial)
    if pd is None:
        return web.json_response({"error": f"Device {serial} not connected"}, status=404)

    scenes = provisioner._scene_profiles(serial)
    scene_list = []
    for i, p in enumerate(scenes):
        name = p.name or f"scene-{i}"
        scene_list.append({
            "name": name,
            "slot_count": len(p.templates.keys),
            "has_touchscreen": len(p.templates.touchscreen) > 0,
        })
    return web.json_response(scene_list)


async def handle_switch_scene(request: web.Request) -> web.Response:
    """Switch the active scene on a device."""
    provisioner: Provisioner = request.app["provisioner"]
    serial = request.match_info["serial"]

    pd = provisioner.active_decks.get(serial)
    if pd is None:
        return web.json_response({"error": f"Device {serial} not connected"}, status=404)

    body = await request.json()
    scene_name = body.get("scene")
    if not scene_name:
        return web.json_response({"error": "Missing 'scene' in body"}, status=400)

    # Validate scene exists
    scenes = provisioner._scene_profiles(serial)
    scene_names = [p.name or f"scene-{i}" for i, p in enumerate(scenes)]
    if scene_name not in scene_names:
        return web.json_response(
            {"error": f"Scene '{scene_name}' not found", "available": scene_names},
            status=404,
        )

    # Switch the deck to the requested scene
    deck = provisioner.get_deck(serial)
    if deck is None:
        return web.json_response({"error": "Deck not available"}, status=500)

    await deck.set_screen(scene_name)
    pd.active_scene = scene_name
    log.info("API: Switched device %s to scene '%s'", serial, scene_name)

    return web.json_response({"serial": serial, "active_scene": scene_name})
