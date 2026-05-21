"""Website Monitor Plugin for Hermes Agent."""

from __future__ import annotations

import json
import logging
import threading
import time
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
    """Loads monitor states from disk.
    Format: { "https://example.com": {"last_status": "UP"} }
    """
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
            return response.status == 200
    except Exception:
        return False


def _background_monitor_loop() -> None:
    """Continuously runs in the background. Alerts only on transitions."""
    # Wait for the gateway process to settle
    time.sleep(15)
    
    logger.info("Website Monitor background thread started.")
    
    while True:
        try:
            monitors = _load_monitors()
            changed = False
            
            for url, info in list(monitors.items()):
                is_up = _check_website(url)
                current_status = "UP" if is_up else "DOWN"
                old_status = info.get("last_status", "UNKNOWN")
                
                # Check for status change transition
                if current_status != old_status:
                    monitors[url]["last_status"] = current_status
                    changed = True
                    
                    # ⚠️ ALERT TRANSITION CHAT TRIGGER
                    if old_status != "UNKNOWN":
                        alert_icon = "🟢" if is_up else "🔴"
                        alert_msg = (
                            f"{alert_icon} **WEBSITE UPTIME MONITOR ALERT**\n\n"
                            f"The website **{url}** went from **{old_status}** ➡️ **{current_status}**!"
                        )
                        
                        # Deliver to the user's active messaging platform's home channel
                        # Supported platforms: 'matrix', 'telegram', 'discord', 'slack'
                        # It will automatically fall back to whichever platform is running!
                        for platform in ["matrix", "telegram", "discord"]:
                            try:
                                # send_message_tool has a built-in async-to-sync runner, making it safe to call here
                                send_message_tool({
                                    "action": "send",
                                    "target": f"{platform}",
                                    "message": alert_msg
                                })
                            except Exception:
                                pass # Suppress if specific platform is not enabled

            if changed:
                _save_monitors(monitors)
                
        except Exception as e:
            logger.error(f"Error in Website Monitor loop: {e}")
# Poll every 60 seconds
        time.sleep(60)


def register(ctx) -> None:
    """Registers tools and fires up the background monitoring thread."""
    from .tools import (
        ADD_MONITOR_SCHEMA,
        REMOVE_MONITOR_SCHEMA,
        LIST_MONITORS_SCHEMA,
        _handle_add_monitor,
        _handle_remove_monitor,
        _handle_list_monitors,
    )
    
    # 1. Register tools into the Website Monitor toolset
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
    
    # 2. Spawn the background polling thread
    monitor_thread = threading.Thread(target=_background_monitor_loop, daemon=True)
    monitor_thread.start()
