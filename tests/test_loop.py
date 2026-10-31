import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QPaintEvent
from PyQt6.QtCore import QRect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from main import PetWindow, PetState

app = QApplication.instance() or QApplication([])

def test_full_loop():
    pet = PetWindow()
    # Simulate 300 ticks of update_logic
    for i in range(300):
        pet.update_logic()

    # Simulate states
    pet.feed_pet()
    assert pet.state == PetState.SATED
    for i in range(60):
        pet.update_logic()

    pet.play_with_pet()
    assert pet.state == PetState.REACTING
    for i in range(50):
        pet.update_logic()

    pet.make_pet_sleep()
    assert pet.state == PetState.SLEEPING
    for i in range(50):
        pet.update_logic()

    pet.wake_up()
    assert pet.state == PetState.IDLE

    # Simulate render
    event = QPaintEvent(QRect(0, 0, 200, 200))
    pet.paintEvent(event)
    print("Loop and render simulation completed successfully!")

if __name__ == "__main__":
    test_full_loop()

