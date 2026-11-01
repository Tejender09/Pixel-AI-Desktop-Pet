import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from src.context_engine import ContextEngine
except ImportError:
    from context_engine import ContextEngine  # type: ignore

def test_context_engine_initialization():
    engine = ContextEngine()
    assert isinstance(engine.app_moods, dict)
    assert "code.exe" in engine.app_moods
    assert engine.app_moods["code.exe"] == "FOCUSED"

def test_get_active_window_info():
    engine = ContextEngine()
    info = engine.get_active_window_info()
    assert isinstance(info, dict)
    assert "title" in info
    assert "process" in info
    assert "hwnd" in info

def test_analyze_context():
    engine = ContextEngine()
    # Should not crash and return string or None
    result = engine.analyze_context()
    assert result is None or isinstance(result, str)
    print("ContextEngine tests passed successfully!")

if __name__ == "__main__":
    test_context_engine_initialization()
    test_get_active_window_info()
    test_analyze_context()

