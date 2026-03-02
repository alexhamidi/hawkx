import json
import os

SETTINGS_DIR = os.path.expanduser("~/.hawkx")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")


def load() -> dict:
    if not os.path.exists(SETTINGS_PATH):
        return {"profile": "1"}
    with open(SETTINGS_PATH) as f:
        return json.load(f)


def save(data: dict) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_profile() -> str:
    return load().get("profile", "1")


def set_profile(profile: str) -> None:
    data = load()
    data["profile"] = profile
    save(data)
