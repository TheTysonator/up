"""Website Monitor Plugin for Hermes Agent."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

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


def _find_socks_port(config: Any) -> Optional[int]:
    """
    Recursively finds a SOCKS inbound listen_port in a sing-box/Hiddify config.
    """
    if isinstance(config, dict):
        if config.get("type") == "socks" and "listen_port" in config:
            return int(config["listen_port"])

        for value in config.values():
            found = _find_socks_port(value)
            if found:
                return found

    elif isinstance(config, list):
        for item in config:
            found = _find_socks_port(item)
            if found:
                return found

    return None


def _check_proxy(name: str, config: Dict[str, Any]) -> bool:
    """
    Starts hiddify-core, waits for local SOCKS proxy, tests through it,
    then shuts it down.
    """
    test_url = config.get("test_url", "https://ifconfig.me")
    socks_port = int(config.get("socks_port", 12334))

    temp_path = None
    proc = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as f:
            json.dump(config, f)
            temp_path = f.name

        proc = subprocess.Popen(
            ["hiddify-core", "run", "-c", temp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Wait for SOCKS port to open
        for _ in range(20):
            result = subprocess.run(
                ["bash", "-lc", f"ss -ltn | grep -q ':{socks_port} '"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if result.returncode == 0:
                break

            time.sleep(1)
        else:
            logger.error(f"Proxy monitor {name}: SOCKS port {socks_port} never opened")
            return False

        # Test through SOCKS5h
        result = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--max-time",
                "15",
                "--proxy",
                f"socks5h://127.0.0.1:{socks_port}",
                test_url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            logger.error(
                f"Proxy monitor {name}: curl failed: {result.stderr.strip()}"
            )
            return False

        logger.info(f"Proxy monitor {name}: test succeeded: {result.stdout.strip()[:120]}")
        return True

    except Exception:
        logger.exception(f"Proxy monitor failed for {name}")
        return False

    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


def _send_alert(ctx, target_room: str, message: str) -> None:
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
    time.sleep(15)

    logger.info("Website Monitor background thread started successfully.")

    target_room = "matrix:!RCoAgzyLWmmeLSIfPF:hmx.sh"

    while True:
        try:
            monitors = _load_monitors()
            changed = False

            for monitor_id, info in list(monitors.items()):
                monitor_type = info.get("type", "website")

                if monitor_type == "proxy":
                    name = info.get("name", monitor_id.replace("proxy:", ""))
                    config = info.get("config", {})

                    is_up = _check_proxy(name, config)
                    display_name = name
                    alert_title = "PROXY MONITOR ALERT"

                else:
                    is_up = _check_website(monitor_id)
                    display_name = monitor_id
                    alert_title = "WEBSITE UPTIME MONITOR ALERT"

                current_status = "UP" if is_up else "DOWN"
                old_status = info.get("last_status", "UNKNOWN")

                if current_status != old_status:
                    monitors[monitor_id]["last_status"] = current_status
                    changed = True

                    logger.info(
                        f"Monitor status changed for {display_name}: "
                        f"{old_status} -> {current_status}"
                    )

                    if old_status != "UNKNOWN":
                        alert_icon = "🟢" if is_up else "🔴"

                        alert_msg = (
                            f"{alert_icon} **{alert_title}**\n\n"
                            f"**{display_name}** went from "
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
        ADD_MONITOR_PROXY_SCHEMA,
        REMOVE_MONITOR_SCHEMA,
        LIST_MONITORS_SCHEMA,
        _handle_add_monitor,
        _handle_add_monitor_proxy,
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
        name="add_monitor_proxy",
        toolset="uptime",
        schema=ADD_MONITOR_PROXY_SCHEMA,
        handler=_handle_add_monitor_proxy,
        emoji="🧦",
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