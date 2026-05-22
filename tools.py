"""Website Monitor Plugin for Hermes Agent."""

from __future__ import annotations

import builtins
import hashlib
import json
import logging
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

if not hasattr(builtins, "_hermes_uptime_thread_started"):
    builtins._hermes_uptime_thread_started = False

if not hasattr(builtins, "_hermes_uptime_thread_lock"):
    builtins._hermes_uptime_thread_lock = threading.Lock()

if not hasattr(builtins, "_hermes_uptime_check_lock"):
    builtins._hermes_uptime_check_lock = threading.Lock()


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


def _stable_port_for_name(name: str, base: int = 12334, spread: int = 1000) -> int:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return base + (int(digest[:8], 16) % spread)


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


def _build_proxy_runtime_config(config: Dict[str, Any], socks_port: int) -> Dict[str, Any]:
    outbounds = config.get("outbounds", [])
    if not outbounds:
        raise ValueError("Proxy config has no outbounds")

    final_tag = outbounds[0].get("tag")
    if not final_tag:
        raise ValueError("First proxy outbound has no tag")

    return {
        "log": {"level": "info"},
        "inbounds": [
            {
                "type": "socks",
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "listen_port": socks_port,
            }
        ],
        "outbounds": outbounds,
        "route": {"final": final_tag},
    }


def _check_proxy(name: str, config: Dict[str, Any]) -> bool:
    test_url = config.get("test_url", "https://api.ipify.org")
    socks_port = int(config.get("socks_port", _stable_port_for_name(name)))

    temp_path = None
    proc = None

    try:
        runtime_config = _build_proxy_runtime_config(config, socks_port)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as f:
            json.dump(runtime_config, f)
            temp_path = f.name

        proc = subprocess.Popen(
            ["hiddify-core", "run", "-c", temp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for _ in range(30):
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

        time.sleep(2)

        result = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--location",
                "--retry",
                "2",
                "--retry-delay",
                "1",
                "--connect-timeout",
                "10",
                "--max-time",
                "25",
                "--proxy",
                f"socks5h://127.0.0.1:{socks_port}",
                test_url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Proxy monitor {name}: curl failed: {result.stderr.strip()}")
            return False

        logger.info(
            f"Proxy monitor {name}: test succeeded via port {socks_port}: "
            f"{result.stdout.strip()[:120]}"
        )
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

    logger.warning(f"RUNNING UPTIME LOOP FROM FILE: {__file__}")
    logger.info("Website Monitor background thread started successfully.")

    target_room = "matrix:!RCoAgzyLWmmeLSIfPF:hmx.sh"

    while True:
        with builtins._hermes_uptime_check_lock:
            try:
                monitors = _load_monitors()
                changed = False

                for monitor_id, info in list(monitors.items()):
                    if not isinstance(info, dict):
                        logger.warning(f"Skipping malformed monitor: {monitor_id}")
                        continue

                    if monitor_id.startswith("proxy:"):
                        monitor_type = "proxy"
                    else:
                        monitor_type = info.get("type", "website")

                    if monitor_type == "proxy":
                        name = info.get("name", monitor_id.replace("proxy:", ""))
                        config = info.get("config", {})

                        is_up = _check_proxy(name, config)
                        display_name = name
                        alert_title = "PROXY MONITOR ALERT"

                    elif monitor_type == "website":
                        if not monitor_id.startswith(("http://", "https://")):
                            logger.warning(f"Skipping invalid website monitor key: {monitor_id}")
                            continue

                        is_up = _check_website(monitor_id)
                        display_name = monitor_id
                        alert_title = "WEBSITE UPTIME MONITOR ALERT"

                    else:
                        logger.warning(f"Skipping unknown monitor type for {monitor_id}: {monitor_type}")
                        continue

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
        ADD_WEBSITE_MONITOR_SCHEMA,
        ADD_PROXY_MONITOR_SCHEMA,
        REMOVE_MONITOR_SCHEMA,
        LIST_MONITORS_SCHEMA,
        _handle_add_website_monitor,
        _handle_add_proxy_monitor,
        _handle_remove_monitor,
        _handle_list_monitors,
    )

    ctx.register_tool(
        name="add_website_monitor",
        toolset="uptime",
        schema=ADD_WEBSITE_MONITOR_SCHEMA,
        handler=_handle_add_website_monitor,
        emoji="➕",
    )

    ctx.register_tool(
        name="add_proxy_monitor",
        toolset="uptime",
        schema=ADD_PROXY_MONITOR_SCHEMA,
        handler=_handle_add_proxy_monitor,
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

    with builtins._hermes_uptime_thread_lock:
        if builtins._hermes_uptime_thread_started:
            logger.info("Website Monitor background thread already running globally; skipping duplicate start.")
            return

        monitor_thread = threading.Thread(
            target=_background_monitor_loop,
            args=(ctx,),
            daemon=True,
        )

        monitor_thread.start()
        builtins._hermes_uptime_thread_started = True

    logger.info("Website Monitor background thread registered successfully.")