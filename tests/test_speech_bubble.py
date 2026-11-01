import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.main import PetWindow, SpeechBubbleWidget
except ImportError:
    from main import PetWindow, SpeechBubbleWidget  # type: ignore

app = QApplication.instance() or QApplication([])

def test_speech_bubble_functionality():
    pet = PetWindow()
    bubble = pet.bubble_widget
    assert isinstance(bubble, SpeechBubbleWidget)

    # Initial state
    assert not bubble.isVisible()

    # Trigger speech
    pet.say("Testing speech bubble!", duration=50)
    assert bubble.isVisible()
    assert bubble.text == "Testing speech bubble!"
    assert bubble.bubble_w > 90
    assert bubble.bubble_h >= 36

    # Test tick pop-in animation
    bubble.tick()
    assert bubble.scale > 0.7
    assert bubble.opacity > 0.0

    # Advance ticks past pop-in
    for _ in range(12):
        bubble.tick()
    assert bubble.scale == 1.0
    assert bubble.opacity == 1.0

    # Advance until near expiration (fade out)
    while bubble.visible_ticks > 10:
        bubble.tick()
    assert bubble.opacity <= 1.0

    # Advance to expiration
    while bubble.visible_ticks > 0:
        bubble.tick()
    bubble.tick() # Final tick to trigger hide
    assert not bubble.isVisible()

    # Test trigger_speech with mood
    pet.trigger_speech("FEED")
    assert bubble.isVisible()
    assert len(bubble.text) > 0

    print("test_speech_bubble_functionality passed successfully!")

if __name__ == "__main__":
    test_speech_bubble_functionality()

