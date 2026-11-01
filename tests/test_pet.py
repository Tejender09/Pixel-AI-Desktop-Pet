import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QRect

# Ensure src is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.main import PetWindow, AnimationManager, PetState
except ImportError:
    from main import PetWindow, AnimationManager, PetState  # type: ignore

# Create or reuse QApplication instance for headless tests
app = QApplication.instance()
if not app:
    app = QApplication([])

def test_animation_manager_loads_all_states():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    manager = AnimationManager(base_dir)

    for state in [PetState.IDLE, PetState.WALKING, PetState.REACTING, PetState.SATED, PetState.SLEEPING]:
        frames = manager.sprites[state]
        assert len(frames) > 0, f"Expected frames for {state}, got 0"
        frame = manager.get_frame(state, 0)
        assert frame is not None
        assert not frame.isNull()
        assert frame.width() == 32
        assert frame.height() == 32

def test_pet_window_initialization():
    pet = PetWindow()
    # Check window size
    assert pet.width() == 200
    assert pet.height() == 200

    # Check window flags
    flags = pet.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint

    # Check translucent background
    assert pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    # Initial state
    assert pet.state == PetState.IDLE
    assert pet.scale_factor == 1.0

def test_hitbox_accuracy():
    pet = PetWindow()
    # Default scale 1.0, bounce 0: 128x128 centered in 200x200
    hitbox = pet.get_hitbox()
    assert hitbox.width() == 128
    assert hitbox.height() == 128
    assert hitbox.x() == (200 - 128) // 2  # 36
    assert hitbox.y() == (200 - 128) // 2  # 36

    # Test with bounce_y
    pet.bounce_y = 20.0
    hitbox_bounced = pet.get_hitbox()
    assert hitbox_bounced.y() == 36 - 20

    # Test with scale_factor
    pet.bounce_y = 0.0
    pet.scale_factor = 1.2
    hitbox_scaled = pet.get_hitbox()
    expected_w = int(128 * 1.2)
    assert hitbox_scaled.width() == expected_w
    assert hitbox_scaled.x() == (200 - expected_w) // 2

def test_needs_system_actions():
    pet = PetWindow()
    init_hunger = pet.hunger
    init_happiness = pet.happiness

    # Feed
    pet.feed_pet()
    assert pet.hunger < init_hunger
    assert pet.happiness >= init_happiness
    assert pet.state == PetState.SATED
    assert pet.target_scale > 1.0

    # Nap
    pet.make_pet_sleep()
    assert pet.state == PetState.SLEEPING
    assert pet.target_scale < 1.0

    # Wake Up
    pet.wake_up()
    assert pet.state == PetState.IDLE
    assert pet.target_scale == 1.0

    # Play
    pet.play_with_pet()
    assert pet.state == PetState.REACTING
    assert pet.reaction_frames > 0

def test_wandering_and_flipping():
    pet = PetWindow()
    pet.start_wandering()
    assert pet.state == PetState.WALKING

    # Manually position pet and target
    pet.move(100, 100)
    pet.target_pos = QPoint(300, 100)
    pet.move_towards_target()
    assert pet.facing_right is True

    pet.target_pos = QPoint(50, 100)
    pet.move_towards_target()
    assert pet.facing_right is False

if __name__ == "__main__":
    test_animation_manager_loads_all_states()
    test_pet_window_initialization()
    test_hitbox_accuracy()
    test_needs_system_actions()
    test_wandering_and_flipping()
    print("All tests passed successfully!")
