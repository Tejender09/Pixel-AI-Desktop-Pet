import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.main import AnimationManager, PetState
except ImportError:
    from main import AnimationManager, PetState  # type: ignore

app = QApplication.instance() or QApplication([])

def test_eye_tracking_integration():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    manager = AnimationManager(base_dir)

    # Test center, left, and right shifts
    pm_center = manager.get_frame(PetState.IDLE, 0, shift_x=0, shift_y=0)
    pm_left = manager.get_frame(PetState.IDLE, 0, shift_x=-1, shift_y=0)
    pm_right = manager.get_frame(PetState.IDLE, 0, shift_x=1, shift_y=0)

    assert pm_center is not None and not pm_center.isNull()
    assert pm_left is not None and not pm_left.isNull()
    assert pm_right is not None and not pm_right.isNull()

    img_center = pm_center.toImage()
    img_left = pm_left.toImage()
    img_right = pm_right.toImage()

    # Left eye x range in frame 0 is [10..14]
    # For center: pupil is at index 12..13
    # For left: pupil is at index 11..12
    # For right: pupil is at index 13..14
    pupil_left_x_center = [x for x in range(10, 15) if img_center.pixelColor(x, 13).red() < 60]
    pupil_left_x_left = [x for x in range(10, 15) if img_left.pixelColor(x, 13).red() < 60]
    pupil_left_x_right = [x for x in range(10, 15) if img_right.pixelColor(x, 13).red() < 60]

    assert pupil_left_x_left[0] < pupil_left_x_center[0], "Pupil should shift left"
    assert pupil_left_x_right[0] > pupil_left_x_center[0], "Pupil should shift right"

    # Verify head-bob synchronization between frame 0 (dy=0) and frame 1 (dy=1)
    frame0_pm = manager.get_frame(PetState.IDLE, 0, shift_x=0, shift_y=0)
    # Frame 1 at speed=12 occurs at frame_count=12
    frame1_pm = manager.get_frame(PetState.IDLE, 12, shift_x=0, shift_y=0)

    f0_img = frame0_pm.toImage()
    f1_img = frame1_pm.toImage()

    f0_pupil_y = [y for y in range(10, 17) if f0_img.pixelColor(12, y).red() < 60]
    f1_pupil_y = [y for y in range(10, 17) if f1_img.pixelColor(12, y).red() < 60]

    assert f1_pupil_y[0] == f0_pupil_y[0] + 1, "Pupil y must shift down with head bob in frame 1"
    print("Eye tracking pixel synchronization test passed!")

if __name__ == "__main__":
    test_eye_tracking_integration()

