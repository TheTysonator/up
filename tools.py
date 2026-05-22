"""Tools for Website Monitor Plugin."""

from __future__ import annotations

import json
from . import _load_monitors, _save_monitors, _check_website


# --- SCHEMAS ---







# Add Website Monitor Schema
ADD_WEBSITE_MONITOR_SCHEMA = {
    "name": "add_website_monitor",
    "description": "Add a website to be monitored.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "This is the name of the monitor."
            },
            "configuration": {
                "type": "STRING",
                "description": "The URL of the website to monitor."
            },
            "application": {
                "type": "STRING",
                "description": "This is the name of the application this monitor is associated with."
            }
        },
        "required": [ "name", "configuration" ]
    }
}


# Add Proxy Monitor Schema
ADD_PROXY_MONITOR_SCHEMA = {
    "name": "add_proxy_monitor",
    "description": "Add a proxy to be monitored.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "This is the name of the monitor."
            },
            "configuration": {
                "type": "OBJECT",
                "description": "This is the configuration object for the monitor."
            },
            "application": {
                "type": "STRING",
                "description": "This is the name of the application this monitor is associated with."
            }
        },
        "required": [ "name", "configuration" ]
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

def _handle_add_website_monitor(args: dict, **kw) -> str:
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


def _handle_add_proxy_monitor(args: dict, **kw) -> str:
    app = args.get("app", "default").strip()
    name = args.get("name", "").strip()
    config = args.get("configuration")

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
