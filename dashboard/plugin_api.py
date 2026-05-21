"""Website Monitor Dashboard Backend API routes.
Mounted at /api/plugins/website-monitor/ by the plugin system.
"""

import json
from pathlib import Path
from fastapi import APIRouter, Query
# 🟢 CORRECT CANONICAL IMPORT FOR DASHBOARD ROUTING
from hermes_cli.config import get_hermes_home

router = APIRouter()

def _get_config_path() -> Path:
    return get_hermes_home() / "website_monitors.json"

def _load_monitors() -> dict:
    path = _get_config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_monitors(monitors: dict) -> None:
    path = _get_config_path()
    try:
        path.write_text(json.dumps(monitors, indent=2), encoding="utf-8")
    except Exception:
        pass


@router.get("/status")
async def status():
    """Returns the list of monitored URLs and their last status."""
    return {"success": True, "monitors": _load_monitors()}


@router.get("/add")
async def add(url: str = Query(...)):
    """Add a new URL to monitoring."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return {"success": False, "error": "URL must begin with http:// or https://"}
    monitors = _load_monitors()
    if url in monitors:
        return {"success": True, "message": "Already monitored."}
    monitors[url] = {"last_status": "UNKNOWN"}
    _save_monitors(monitors)
    return {"success": True, "message": f"Added {url}."}


@router.get("/remove")
async def remove(url: str = Query(...)):
    """Remove a URL from monitoring."""
    url = url.strip()
    monitors = _load_monitors()
    if url not in monitors:
        return {"success": False, "error": "Not monitored."}
    del monitors[url]
    _save_monitors(monitors)
    return {"success": True, "message": f"Removed {url}."}
