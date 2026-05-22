"""Tools for Website Monitor Plugin."""

from __future__ import annotations

import json
from . import _load_monitors, _save_monitors, _check_website


# --- SCHEMAS ---


ADD_MONITOR_PROXY_SCHEMA = {
    "name": "add_monitor_proxy",
    "description": "Add a PROXY to the background monitoring queue.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "This is the name of the monitor."},
            "config": {"type": "OBJECT", "description": "This is the configuration object for the monitor."},
            "app": {"type": "STRING", "description": "This is the name of the app this monitor is associated with."}
        },
        "required": ["name", "config"]
    }
}


ADD_MONITOR_SCHEMA = {
    "name": "add_monitor",
    "description": "Add a website URL to the background monitoring queue.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app": {"type": "STRING", "description": "This is the name of the app this monitor is associated with."},
            "url": {"type": "STRING", "description": "The absolute URL to monitor (e.g. https://google.com)"}
        },
        "required": ["url"]
    }
}

REMOVE_MONITOR_SCHEMA = {
    "name": "remove_monitor",
    "description": "Remove a website URL from background monitoring.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "The exact URL to remove from monitors."}
        },
        "required": ["url"]
    }
}

LIST_MONITORS_SCHEMA = {
    "name": "list_monitors",
    "description": "List all currently monitored websites and their active status.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}


# --- HANDLERS ---

def _handle_add_monitor(args: dict, **kw) -> str:
    app = args.get("app", "default").strip()
    url = args.get("url", "").strip()
    if not url.startswith(("http://", "https://")):
        return json.dumps({"success": False, "error": "URL must begin with http:// or https://"})
        
    monitors = _load_monitors()
    if url in monitors:
        return json.dumps({"success": True, "message": f"{url} is already being monitored."})
        
    # Seed with UNKNOWN so the loop checks it and transitions state
    monitors[url] = {"last_status": "UNKNOWN", "app": app}
    _save_monitors(monitors)
    return json.dumps({"success": True, "message": f"Successfully added {url} to the website monitor."})


def _handle_add_monitor_proxy(args: dict, **kw) -> str:
    app = args.get("app", "default").strip()
    name = args.get("name", "").strip()
    config = args.get("config")

    if not name:
        return json.dumps({"success": False, "error": "Proxy monitor name is required."})

    if not isinstance(config, dict):
        return json.dumps({"success": False, "error": "Proxy config must be a JSON object."})

    monitors = _load_monitors()

    monitor_key = f"proxy:{name}"

    if monitor_key in monitors:
        return json.dumps({"success": True, "message": f"{name} is already being monitored."})

    monitors[monitor_key] = {
        "type": "proxy",
        "name": name,
        "app": app,
        "config": config,
        "last_status": "UNKNOWN"
    }

    _save_monitors(monitors)

    return json.dumps({
        "success": True,
        "message": f"Successfully added proxy monitor {name}."
    })



def _handle_remove_monitor(args: dict, **kw) -> str:
    url = args.get("url", "").strip()
    monitors = _load_monitors()
    
    if url not in monitors:
        return json.dumps({"success": False, "error": f"{url} is not in the monitored websites list."})
        
    del monitors[url]
    _save_monitors(monitors)
    return json.dumps({"success": True, "message": f"Successfully removed {url} from monitoring."})


def _handle_list_monitors(args: dict, **kw) -> str:
    monitors = _load_monitors()
    if not monitors:
        return json.dumps({"success": True, "message": "No websites are currently being monitored."})
        
    return json.dumps({"success": True, "monitors": monitors})
