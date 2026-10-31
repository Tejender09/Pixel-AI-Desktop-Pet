import os
import json
import time
from typing import Dict, Any, Optional


class MemoryStore:
    """
    Manages long-term persistence and bonding for the Desktop Pet.
    Stores interaction history, favorite apps, time spent together, and bond progression.
    """
    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_data"))
            os.makedirs(base_dir, exist_ok=True)
            self.filepath = os.path.join(base_dir, "pet_memory.json")
        else:
            self.filepath = filepath
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        self.data: Dict[str, Any] = {
            "pet_name": "Pixel",
            "created_at": time.time(),
            "total_time_seconds": 0,
            "bond_level": 10,  # 0 to 100
            "app_time_spent": {},  # process_name: seconds
            "feed_count": 0,
            "play_count": 0,
            "last_seen": time.time()
        }
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        self.data.update(saved)
            except Exception as e:
                print(f"MemoryStore Warning: Failed to read {self.filepath}, using defaults ({e})")

    def save(self):
        try:
            self.data["last_seen"] = time.time()
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"MemoryStore Error: Failed to write {self.filepath}: {e}")

    def record_app_time(self, process_name: str, seconds: int = 1):
        if not process_name:
            return
        clean_proc = process_name.lower().strip()
        app_times = self.data.setdefault("app_time_spent", {})
        app_times[clean_proc] = app_times.get(clean_proc, 0) + seconds
        self.data["total_time_seconds"] = self.data.get("total_time_seconds", 0) + seconds

        # Gradual bond growth from spending time together (every 100 seconds +1 bond)
        if self.data["total_time_seconds"] % 120 == 0:
            self.increment_bond(1)

    def record_interaction(self, action_type: str):
        if action_type == "feed":
            self.data["feed_count"] = self.data.get("feed_count", 0) + 1
            self.increment_bond(2)
        elif action_type == "play":
            self.data["play_count"] = self.data.get("play_count", 0) + 1
            self.increment_bond(3)

    def increment_bond(self, amount: int = 1):
        self.data["bond_level"] = min(100, max(0, self.data.get("bond_level", 0) + amount))

    @property
    def bond_level(self) -> int:
        return int(self.data.get("bond_level", 10))

    @property
    def pet_name(self) -> str:
        return str(self.data.get("pet_name", "Pixel"))

    def get_favorite_app(self) -> str:
        app_times = self.data.get("app_time_spent", {})
        if not app_times:
            return "None yet"
        # Return app with the most time spent
        fav = max(app_times.items(), key=lambda item: item[1])[0]
        # Clean extension for display (e.g. code.exe -> VS Code, spotify.exe -> Spotify)
        friendly_names = {
            "code.exe": "VS Code",
            "chrome.exe": "Chrome",
            "msedge.exe": "Edge",
            "spotify.exe": "Spotify",
            "discord.exe": "Discord",
            "devenv.exe": "Visual Studio",
            "pycharm64.exe": "PyCharm"
        }
        return friendly_names.get(fav, fav.replace(".exe", "").title())

