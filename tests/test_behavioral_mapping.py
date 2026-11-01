import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from context_engine import ContextEngine

def test_semantic_keywords_mapping():
    engine = ContextEngine()

    # Test title keywords
    engine.last_window_title = ""
    engine.last_process = ""
    # Fake info method for testing logic
    def mock_info(title, process):
        return {"title": title, "process": process, "hwnd": 1, "rect": (100, 100, 800, 600)}

    engine.get_active_window_info = lambda: mock_info("Video - YouTube - Google Chrome", "chrome.exe")
    assert engine.analyze_context() == "WATCHING"

    engine.get_active_window_info = lambda: mock_info("DEBUG [Error] in main.py - Visual Studio Code", "code.exe")
    assert engine.analyze_context() == "WORRIED"

    # When Spotify is open AND audio is playing -> GROOVING
    engine.is_audio_playing = lambda: True
    engine.get_active_window_info = lambda: mock_info("Daft Punk - Spotify Premium", "spotify.exe")
    assert engine.analyze_context() == "GROOVING"

    # When Spotify/Music tab is open BUT audio is paused/silent -> IDLE (no false grooving!)
    engine.is_audio_playing = lambda: False
    engine.last_window_title = ""
    engine.last_process = ""
    engine.get_active_window_info = lambda: mock_info("Paused Song - Spotify", "spotify.exe")
    assert engine.analyze_context() == "IDLE"

    # When normal video (YouTube/tutorial/movie) is playing with sound -> WATCHING (watching attentively, not dancing!)
    engine.is_audio_playing = lambda: True
    engine.last_window_title = ""
    engine.last_process = ""
    engine.get_active_window_info = lambda: mock_info("Python Full Course - YouTube", "chrome.exe")
    assert engine.analyze_context() == "WATCHING"

    # When concert / music video is playing with sound -> GROOVING (dancing along!)
    engine.last_window_title = ""
    engine.last_process = ""
    engine.get_active_window_info = lambda: mock_info("Live Concert 2026 - YouTube", "chrome.exe")
    assert engine.analyze_context() == "GROOVING"

    engine.get_active_window_info = lambda: mock_info("main.py - Visual Studio Code", "code.exe")
    assert engine.analyze_context() == "FOCUSED"

    print("test_semantic_keywords_mapping passed!")

if __name__ == "__main__":
    test_semantic_keywords_mapping()

