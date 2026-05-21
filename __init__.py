"""Website Monitor Plugin for Hermes Agent."""

# uptime, polaris, plugin room

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


def _get_config_path() -> Path:
    return get_hermes_home() / "website_monitors.json"


def _load_monitors() -> Dict[str, Dict[str, Any]]:
    path = _get_config_path()

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read website monitors config: {e}")
        return {}


def _save_monitors(monitors: Dict[str, Dict[str, Any]]) -> None:
    path = _get_config_path()

    try:
        path.write_text(json.dumps(monitors, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write website monitors config: {e}")


def _check_website(url: str) -> bool:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Hermes-Website-Monitor/1.0"},
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300

    except Exception:
        return False


def _send_alert(ctx, target_room: str, message: str) -> None:
    """
    Sends a Hermes message using the plugin context.

    Do NOT import gateway.run.gateway directly here.
    The ctx object is the correct bridge back into Hermes.
    """
    try:
        result = ctx.dispatch_tool(
            "send_message",
            {
                "target": target_room,
                "message": message,
            },
        )

        logger.info(f"Website monitor alert dispatched: {result}")

    except Exception:
        logger.exception("Failed to dispatch website monitor alert")


def _background_monitor_loop(ctx) -> None:
    """
    Continuously checks websites in the background.

    Alerts only when a monitor changes from UP -> DOWN or DOWN -> UP.
    """
    time.sleep(15)

    logger.info("Website Monitor background thread started successfully.")

    target_room = "matrix:!RCoAgzyLWmmeLSIfPF:hmx.sh"

    while True:
        try:
            monitors = _load_monitors()
            changed = False

            for url, info in list(monitors.items()):
                is_up = _check_website(url)

                current_status = "UP" if is_up else "DOWN"
                old_status = info.get("last_status", "UNKNOWN")

                if current_status != old_status:
                    monitors[url]["last_status"] = current_status
                    changed = True

                    logger.info(
                        f"Monitor status changed for {url}: "
                        f"{old_status} -> {current_status}"
                    )

                    # Do not alert on first-ever check.
                    if old_status != "UNKNOWN":
                        alert_icon = "🟢" if is_up else "🔴"

                        alert_msg = (
                            f"{alert_icon} **WEBSITE UPTIME MONITOR ALERT**\n\n"
                            f"The website **{url}** went from "
                            f"**{old_status}** ➡️ **{current_status}**!"
                        )

                        _send_alert(ctx, target_room, alert_msg)

            if changed:
                _save_monitors(monitors)

        except Exception:
            logger.exception("Error in Website Monitor loop")

        time.sleep(60)


def register(ctx) -> None:
    """Registers tools and starts the background monitoring thread."""
    from .tools import (
        ADD_MONITOR_SCHEMA,
        REMOVE_MONITOR_SCHEMA,
        LIST_MONITORS_SCHEMA,
        _handle_add_monitor,
        _handle_remove_monitor,
        _handle_list_monitors,
    )

    ctx.register_tool(
        name="add_monitor",
        toolset="uptime",
        schema=ADD_MONITOR_SCHEMA,
        handler=_handle_add_monitor,
        emoji="➕",
    )

    ctx.register_tool(
        name="remove_monitor",
        toolset="uptime",
        schema=REMOVE_MONITOR_SCHEMA,
        handler=_handle_remove_monitor,
        emoji="❌",
    )

    ctx.register_tool(
        name="list_monitors",
        toolset="uptime",
        schema=LIST_MONITORS_SCHEMA,
        handler=_handle_list_monitors,
        emoji="📋",
    )

    monitor_thread = threading.Thread(
        target=_background_monitor_loop,
        args=(ctx,),
        daemon=True,
    )

    monitor_thread.start()

    logger.info("Website Monitor background thread registered successfully.")