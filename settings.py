"""Small persistent app settings, stored in settings.json next to the app."""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULTS = {
    "bot_ble_address": None,   # None = find the bot's Bluetooth module automatically
    "lidar_rotation": 0,       # degrees added so the bot's front is at the top of the view
    "lidar_port": None,        # None = USB-TTL adapter; or "socket://<ip>:<port>" for WiFi
    "obstacle_stop": True,
    "obstacle_stop_mm": 350,
}


def load():
    data = dict(DEFAULTS)
    try:
        with open(PATH) as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    return data


def save(data):
    with open(PATH, "w") as f:
        json.dump(data, f, indent=2)
