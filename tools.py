"""Tools for Website Monitor Plugin."""

from __future__ import annotations

import json
import re
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


# List Monitors Schema
LIST_MONITORS_SCHEMA = {
    "name": "list_monitors",
    "description": "List all monitored websites and proxies.",
    "parameters": {
        "type": "OBJECT",
        "properties": {}
    }
}


# Remove Monitor Schema
REMOVE_MONITOR_SCHEMA = {
    "name": "remove_monitor",
    "description": "Remove a service from being monitored.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "The name of the monitor to remove."
            },
            "application": {
                "type": "STRING",
                "description": "The application associated with the monitor to remove."
            }
        },
        "required": [ "name", "application" ]
    }
}


# Handle Add Website Monitor
def _handle_add_website_monitor ( args: dict, **kw ) -> str :
    # Input Data
    name = args.get("name", "").strip()
    configuration = args.get("configuration", "").strip()
    application = args.get("application", "Unassigned").strip()
    # Input Data Validation
    if not re.fullmatch(r"^[a-zA-Z0-9 ]+$", name):
        return json.dumps({
            "success": False,
            "error": "Monitor name must be an alphanumeric string that can include spaces."
        })
    if not re.fullmatch(r"^[a-zA-Z0-9 ]+$", application):
        return json.dumps({
            "success": False,
            "error": "Monitor application must be an alphanumeric string that can include spaces."
        })
    # Load Monitors
    monitors = _load_monitors()
    # Check For Duplicates
    if f"{ application}:{ name }" in monitors:
        return json.dumps({
            "success": True,
            "message": f"{ configuration } is already being monitored under { application }."
        })
    # Add Monitor
    monitors[f"{ application }:{ name }"] = {
        "type": "website",
        "configuration": configuration,
        "last_status": "Unknown"
    }
    _save_monitors(monitors)
    return json.dumps({
        "success": True,
        "message": f"Successfully added the monitor for { configuration }."}
    )


# Handle Add Proxy Monitor
def _handle_add_proxy_monitor ( args: dict, **kw ) -> str :
    # Input Data
    name = args.get("name", "").strip()
    configuration = args.get("configuration", "").strip()
    application = args.get("application", "Unassigned").strip()
    # Input Data Validation
    if not re.fullmatch(r"^[a-zA-Z0-9 ]+$", name):
        return json.dumps({
            "success": False,
            "error": "Monitor name must be an alphanumeric string that can include spaces."
        })
    if not re.fullmatch(r"^[a-zA-Z0-9 ]+$", application):
        return json.dumps({
            "success": False,
            "error": "Monitor application must be an alphanumeric string that can include spaces."
        })
    # Load Monitors
    monitors = _load_monitors()
    # Check For Duplicates
    if f"{ application }:{ name }" in monitors:
        return json.dumps({
            "success": True,
            "message": f"{ name } is already being monitored under { application }."
        })
    # Add Monitor
    monitors[f"{ application }: { name }"] = {
        "type": "proxy",
        "configuration": configuration,
        "last_status": "Unknown"
    }
    _save_monitors(monitors)
    return json.dumps({
        "success": True,
        "message": f"Successfully added the proxy monitor for the { name }."
    })


# Handle List Monitors
def _handle_list_monitors ( args: dict, **kw ) -> str :
    # Load Monitors
    monitors = _load_monitors()
    # Return Monitors
    return json.dumps({
        "success": True,
        "monitors": monitors
    })


# Handle Remove Monitor
def _handle_remove_monitor ( args: dict, **kw ) -> str :
    # Input Data
    name = args.get("name", "").strip()
    application = args.get("application", "").strip()
    # Input Data Validation
    if not re.fullmatch(r"^[a-zA-Z0-9 ]+$", name):
        return json.dumps({
            "success": False,
            "error": "Monitor name must be an alphanumeric string that can include spaces."
        })
    if not re.fullmatch(r"^[a-zA-Z0-9 ]+$", application):
        return json.dumps({
            "success": False,
            "error": "Monitor application must be an alphanumeric string that can include spaces."
        })
    # Load Monitors
    monitors = _load_monitors()
    # Find Monitor
    if f"{ application }:{ name }" not in monitors:
        return json.dumps({
            "success": True,
            "error": f"{ name } is not in the monitored under { application }."
        })
    # Remove Monitor
    del monitors[f"{ application }:{ name }"]
    _save_monitors(monitors)
    return json.dumps({
        "success": True,
        "message": f"Successfully removed { name } from being monitored."
    })