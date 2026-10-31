import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from context_engine import ContextEngine

def test_perch_target_calculation():
    engine = ContextEngine()

    # Mock an active window at (200, 200, 1000, 800)
    engine.get_active_window_info = lambda: {
        "title": "Code",
        "process": "code.exe",
        "hwnd": 123,
        "rect": (200, 200, 1000, 800)
    }

    target = engine.get_perch_target(1920, 1080, pet_w=200, pet_h=200)
    assert target is not None
    tx, ty = target
    # Target must be clamped within screen bounds
    assert 10 <= tx <= 1920 - 200 - 10
    assert 10 <= ty <= 1080 - 200 - 10

    center = engine.get_window_center()
    assert center == (600, 500)

    print("test_perch_target_calculation passed!")

if __name__ == "__main__":
    test_perch_target_calculation()

