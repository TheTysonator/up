"""Website Monitor Plugin for Hermes Agent."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import urllib.request
from pathlib import Path
from typing import Any, Dict

# Import profile-safe paths from Hermes
from hermes_constants import get_hermes_home
from tools.send_message_tool import send_message_tool

logger = logging.getLogger(__name__)

# Config files are saved under the active Hermes home profile folder
def _get_config_path() -> Path:
    return get_hermes_home() / "website_monitors.json"


def _load_monitors() -> Dict[str, Dict[str, Any]]:
    """Loads monitor states from disk."""
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
    """Performs a lightweight HTTP GET with a 5-second timeout."""
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Hermes-Website-Monitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


async def _async_background_monitor_loop() -> None:
    """Continuously runs in the background. Alerts only on transitions."""
    # Wait for the gateway process to settle
    await asyncio.sleep(15)
    
    logger.info("Website Monitor background task started (Async).")
    
    while True:
        try:
            # Load monitors in a thread pool to avoid blocking the loop
            monitors = await asyncio.to_thread(_load_monitors)
            changed = False
            
            for url, info in list(monitors.items()):
                # Check website in a thread pool to keep gateway snappy
                is_up = await asyncio.to_thread(_check_website, url)
                current_status = "UP" if is_up else "DOWN"
                old_status = info.get("last_status", "UNKNOWN")
                
                # Check for status change transition
                if current_status != old_status:
                    monitors[url]["last_status"] = current_status
                    changed = True
                    
                    # Alert if transitioning from a known state OR if it initially fails
                    if old_status != "UNKNOWN" or current_status == "DOWN":
                        # Target your specific home room directly from the logs
                        target_room = "matrix:!oyulNhNylFWzeCsVXk:hmx.sh"
                        
                        alert_icon = "🟢" if is_up else "🔴"
                        alert_msg = (
                            f"{alert_icon} **WEBSITE UPTIME MONITOR ALERT**\n\n"
                            f"The website **{url}** went from **{old_status}** ➡️ **{current_status}**!"
                        )
                        
                        try:
                            # 1. Prepare the payload
                            payload = {
                                "action": "send",
                                "target": target_room,
                                "message": alert_msg
                            }
                            
                            # 2. Get the gateway's main event loop
                            main_loop = asyncio.get_event_loop()
                            
                            # 3. Safely schedule the send task on the main thread's loop
                            if main_loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    send_message_tool(payload), 
                                    main_loop
                                )
                            else:
                                # Fallback if called before loop is fully running
                                send_message_tool(payload)
                                
                        except Exception as e:
                            logger.error(f"Failed to send uptime alert: {e}")


            if changed:
                await asyncio.to_thread(_save_monitors, monitors)
                
        except Exception as e:
            logger.error(f"Error in Website Monitor loop: {e}")

        # Sleep asynchronously for 60 seconds (non-blocking)
        await asyncio.sleep(60)


def register(ctx) -> None:
    """Registers tools and fires up the background monitoring task."""
    from .tools import (
        ADD_MONITOR_SCHEMA,
        REMOVE_MONITOR_SCHEMA,
        LIST_MONITORS_SCHEMA,
        _handle_add_monitor,
        _handle_remove_monitor,
        _handle_list_monitors,
    )
    
    # 1. Register tools
    ctx.register_tool(
        name="add_monitor",
        toolset="website_monitor",
        schema=ADD_MONITOR_SCHEMA,
        handler=_handle_add_monitor,
        emoji="➕"
    )
    ctx.register_tool(
        name="remove_monitor",
        toolset="website_monitor",
        schema=REMOVE_MONITOR_SCHEMA,
        handler=_handle_remove_monitor,
        emoji="❌"
    )
    ctx.register_tool(
        name="list_monitors",
        toolset="website_monitor",
        schema=LIST_MONITORS_SCHEMA,
        handler=_handle_list_monitors,
        emoji="📋"
    )
    
    # 2. Schedule the background task on the main running event loop
    loop = asyncio.get_event_loop()
    loop.create_task(_async_background_monitor_loop())
    logger.info("Website Monitor task scheduled successfully on event loop.")

    try:

        send_message_tool({
            "action": "send",
            "target": "matrix:!oyulNhNylFWzeCsVXk:hmx.sh",
            "message": "✅ Website Monitor Plugin has been registered and is now active!"
        })
    except Exception as e:
        logger.error(f"Error in Website Monitor loop: {e}")
