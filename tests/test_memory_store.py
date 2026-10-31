import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from memory_store import MemoryStore

def test_memory_store_lifecycle():
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, "test_memory.json")
    try:
        store = MemoryStore(temp_file)
        assert store.bond_level == 10
        assert store.pet_name == "Pixel"
        assert store.get_favorite_app() == "None yet"

        # Record interactions
        store.record_app_time("code.exe", 30)
        store.record_app_time("spotify.exe", 10)
        store.record_interaction("feed")
        store.record_interaction("play")

        assert store.bond_level > 10
        assert store.get_favorite_app() == "VS Code"

        store.save()
        assert os.path.exists(temp_file)

        # Reload from disk
        store2 = MemoryStore(temp_file)
        assert store2.bond_level == store.bond_level
        assert store2.get_favorite_app() == "VS Code"
        assert store2.data["feed_count"] == 1
        assert store2.data["play_count"] == 1
        print("test_memory_store_lifecycle passed!")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_memory_store_lifecycle()

