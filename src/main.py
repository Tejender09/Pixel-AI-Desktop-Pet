import sys
import random
import math
import os
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QPoint, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor, QPixmap, QTransform, QCursor

# Import generator to create sprites on-the-fly if missing
try:
    from generate_sprites import generate_all_sprites
except ImportError:
    from src.generate_sprites import generate_all_sprites


class PetState:
    IDLE = "IDLE"
    WALKING = "WALKING"
    REACTING = "REACTING"
    SATED = "SATED"
    SLEEPING = "SLEEPING"


class AnimationManager:
    """
    Loads and manages animated sprites for all pet states.
    Supports single spritesheets (e.g. 128x32 horizontal strip)
    as well as individual 32x32 frame sequences (e.g. 01.png, 02.png).
    
    Eye tracking is baked directly into the 32x32 sprite frames so the eye
    pixels are 100% locked to the head, body, bobbing, and pixel grid.
    """
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.frame_size = 32
        self.sprites = {
            PetState.IDLE: [],
            PetState.WALKING: [],
            PetState.REACTING: [],
            PetState.SATED: [],
            PetState.SLEEPING: []
        }
        # Cache for tracked frames: (state, frame_idx, shift_x, shift_y) -> QPixmap
        self.tracked_cache = {}
        self.load_assets()

    def load_assets(self):
        sprites_dir = os.path.join(self.base_path, "sprites")
        
        # Verify or auto-generate assets if directory is missing or empty
        if not os.path.exists(sprites_dir) or not os.listdir(sprites_dir):
            print("Sprites not found, auto-generating pixel art...")
            generate_all_sprites(sprites_dir)

        state_folder_map = {
            PetState.IDLE: ["idle", "idle_sheet.png", "Black-Idle.png"],
            PetState.WALKING: ["walk", "walk_sheet.png", "Black-Run.png"],
            PetState.REACTING: ["react", "react_sheet.png", "01.png"],
            PetState.SATED: ["sated", "sated_sheet.png"],
            PetState.SLEEPING: ["sleep", "sleep_sheet.png"]
        }

        for state, lookups in state_folder_map.items():
            folder_name = lookups[0]
            folder_path = os.path.join(sprites_dir, folder_name)
            frames = []

            # 1. Try loading from spritesheet
            sheet_candidates = [
                os.path.join(sprites_dir, f"{folder_name}_sheet.png"),
                os.path.join(sprites_dir, f"{folder_name}.png"),
                os.path.join(folder_path, "spritesheet.png"),
                os.path.join(folder_path, f"{folder_name}_sheet.png"),
                os.path.join(folder_path, f"{folder_name}.png"),
                os.path.join(folder_path, lookups[-1])
            ]

            sheet_loaded = False
            for sheet_path in sheet_candidates:
                if os.path.exists(sheet_path):
                    pixmap = QPixmap(sheet_path)
                    if not pixmap.isNull():
                        w, h = pixmap.width(), pixmap.height()
                        if w > self.frame_size and h == self.frame_size:
                            cols = w // self.frame_size
                            for c in range(cols):
                                frame = pixmap.copy(c * self.frame_size, 0, self.frame_size, self.frame_size)
                                if not frame.isNull():
                                    frames.append(frame)
                            sheet_loaded = True
                            break

            # 2. If no multi-frame spritesheet loaded, load individual frame files
            if not sheet_loaded and os.path.isdir(folder_path):
                frame_files = sorted([
                    f for f in os.listdir(folder_path)
                    if f.lower().endswith(".png") and not f.lower().startswith("spritesheet")
                ])
                for fname in frame_files:
                    fpath = os.path.join(folder_path, fname)
                    pm = QPixmap(fpath)
                    if not pm.isNull():
                        if pm.width() == self.frame_size and pm.height() == self.frame_size:
                            frames.append(pm)
                        elif pm.width() > self.frame_size:
                            cols = pm.width() // self.frame_size
                            for c in range(cols):
                                frame = pm.copy(c * self.frame_size, 0, self.frame_size, self.frame_size)
                                frames.append(frame)

            self.sprites[state] = frames
            print(f"Loaded {len(frames)} frames for {state}")

    def _create_tracked_frame(self, base_pixmap: QPixmap, shift_x: int, shift_y: int) -> QPixmap:
        """
        Dynamically applies pupil position inside the sprite's white eye sockets
        at the 32x32 pixel level. This guarantees the pupil is part of the sprite,
        perfectly locked to head movement, and strictly on the pixel grid.
        """
        img = base_pixmap.toImage()

        # Find eye socket pixels in upper portion of sprite (y < 22)
        eye_pixels = []
        for y in range(0, min(22, img.height())):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                # Socket white (rgb > 240) or existing pupil dark (rgb < 60)
                if (c.red() > 240 and c.green() > 240 and c.blue() > 240) or \
                   (c.red() < 60 and c.green() < 60 and c.blue() < 60 and c.alpha() > 200):
                    eye_pixels.append((x, y))

        if not eye_pixels:
            return base_pixmap

        # Cluster into left and right eyes (threshold at x = 16)
        left_eye = [p for p in eye_pixels if p[0] < 16]
        right_eye = [p for p in eye_pixels if p[0] >= 16]
        eyes = [e for e in [left_eye, right_eye] if e]

        white_color = QColor(255, 255, 255, 255)
        pupil_color = QColor(30, 30, 40, 255)

        for e in eyes:
            min_x = min(p[0] for p in e)
            max_x = max(p[0] for p in e)
            min_y = min(p[1] for p in e)
            max_y = max(p[1] for p in e)

            # Clear socket back to solid white
            for py in range(min_y, max_y + 1):
                for px in range(min_x, max_x + 1):
                    if (px, py) in e:
                        img.setPixelColor(px, py, white_color)

            # Center of socket
            cx = (min_x + max_x) // 2
            cy = (min_y + max_y) // 2

            # Place 2x2 pupil with shift, clamped so it stays inside socket
            px = max(min_x, min(max_x - 1, cx + shift_x))
            py = max(min_y, min(max_y - 1, cy + shift_y))

            img.setPixelColor(px, py, pupil_color)
            img.setPixelColor(px + 1, py, pupil_color)
            img.setPixelColor(px, py + 1, pupil_color)
            img.setPixelColor(px + 1, py + 1, pupil_color)

        return QPixmap.fromImage(img)

    def get_frame(self, state: str, frame_count: int, shift_x: int = 0, shift_y: int = 0) -> QPixmap:
        frames = self.sprites.get(state, [])
        if not frames:
            frames = self.sprites.get(PetState.IDLE, [])
            if not frames:
                return None
        
        speed_map = {
            PetState.IDLE: 12,
            PetState.WALKING: 6,
            PetState.REACTING: 5,
            PetState.SATED: 8,
            PetState.SLEEPING: 16
        }
        speed = speed_map.get(state, 8)
        idx = (frame_count // speed) % len(frames)

        # In SLEEPING and SATED states, eyes are closed lines (^.^ or - -)
        if state in [PetState.SLEEPING, PetState.SATED]:
            return frames[idx]

        # Use cached pixel-tracked frame
        cache_key = (state, idx, shift_x, shift_y)
        if cache_key not in self.tracked_cache:
            self.tracked_cache[cache_key] = self._create_tracked_frame(frames[idx], shift_x, shift_y)
        return self.tracked_cache[cache_key]


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Requirement 1: Frameless, stays-on-top, translucent background, fixed 200x200
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(200, 200)
        self.setMouseTracking(True)

        # Asset loading with portable directory resolution
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self.animator = AnimationManager(base_dir)

        # Initial positioning
        screen = QApplication.primaryScreen().availableGeometry()
        init_x = min(300, max(50, screen.width() - 250))
        init_y = min(300, max(50, screen.height() - 250))
        self.move(init_x, init_y)

        # State management
        self.state = PetState.IDLE
        self.target_pos = QPoint(self.x(), self.y())
        self.facing_right = True
        self.walk_speed = 2.0
        self.idle_counter = 0
        self.idle_target_time = random.randint(120, 240)

        # Mouse Dragging state
        self.is_dragging = False
        self.drag_offset = QPoint(0, 0)

        # Reaction & Pop animation timers
        self.reaction_frames = 0
        self.pop_animation_frames = 0

        # Needs system: Hunger & Happiness
        self.hunger = 15      # 0 to 100 (increases over time)
        self.happiness = 85   # 0 to 100 (decreases slowly over time)
        self.sleep_timer = 0

        # Animation "Juice" variables
        self.frame_count = 0
        self.bounce_y = 0.0
        self.scale_factor = 1.0
        self.target_scale = 1.0
        self.squash_stretch_x = 1.0
        self.squash_stretch_y = 1.0

        # Eye tracking relative shift on 32x32 sprite grid (-1, 0, 1)
        self.eye_shift_x = 0
        self.eye_shift_y = 0

        # Requirement 3: Heartbeat QTimer (30ms ~ 33 FPS)
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.update_logic)
        self.heartbeat.start(30)

    # -------------------------------------------------------------
    # Hitbox & Geometry
    # -------------------------------------------------------------
    def get_hitbox(self) -> QRect:
        """
        Requirement 3: Accurate interaction hitbox matching the scaled
        and bounced sprite position in local widget coordinates.
        """
        sw = int(128 * self.scale_factor * self.squash_stretch_x)
        sh = int(128 * self.scale_factor * self.squash_stretch_y)
        x = (self.width() - sw) // 2
        y = (self.height() - sh) // 2 - int(self.bounce_y)
        return QRect(x, y, sw, sh)

    def get_grounded_hitbox(self) -> QRect:
        """
        Grounded hitbox (without vertical bounce) used for hover detection
        to prevent jumping jitter when the mouse rests over the pet.
        """
        sw = int(128 * self.scale_factor)
        sh = int(128 * self.scale_factor)
        x = (self.width() - sw) // 2
        y = (self.height() - sh) // 2
        return QRect(x, y, sw, sh)

    # -------------------------------------------------------------
    # Main Heartbeat Update Loop
    # -------------------------------------------------------------
    def update_logic(self):
        self.frame_count += 1

        # 1. Needs System Tick
        if self.frame_count % 100 == 0:
            self.hunger = min(100, self.hunger + 1)
        if self.frame_count % 200 == 0:
            if self.hunger > 60:
                self.happiness = max(0, self.happiness - 2)
            else:
                self.happiness = max(0, self.happiness - 1)

        # 2. Sleeping & Sated Timers
        if self.state == PetState.SLEEPING:
            self.sleep_timer -= 1
            if self.sleep_timer <= 0:
                self.wake_up()

        if self.state == PetState.SATED:
            if self.pop_animation_frames > 0:
                self.pop_animation_frames -= 1
            else:
                self.state = PetState.IDLE

        # 3. Reaction Jump Countdown
        if self.reaction_frames > 0:
            self.reaction_frames -= 1
            if self.reaction_frames <= 0 and not self.is_dragging:
                self.state = PetState.IDLE

        # 4. Mouse Position & Eye Tracking Vector
        cursor_global = QCursor.pos()
        cursor_local = self.mapFromGlobal(cursor_global)
        hitbox = self.get_grounded_hitbox()
        face_center_x = hitbox.x() + hitbox.width() // 2
        face_center_y = hitbox.y() + int(hitbox.height() * 0.4)

        dx = cursor_local.x() - face_center_x
        dy = cursor_local.y() - face_center_y

        # Screen-space direction: -1 (left), 0 (center), +1 (right)
        screen_sx = -1 if dx < -25 else (1 if dx > 25 else 0)
        self.eye_shift_y = -1 if dy < -25 else (1 if dy > 25 else 0)
        
        # When sprite is horizontally flipped, invert x so eyes look toward mouse
        self.eye_shift_x = screen_sx if self.facing_right else -screen_sx

        # 5. Hover Detection
        is_hovered = hitbox.contains(cursor_local)
        if is_hovered and not self.is_dragging:
            if self.state in [PetState.IDLE, PetState.WALKING]:
                self.trigger_reaction()

        # 6. Procedural Animation "Juice" (Sine Waves & Dynamic Scaling)
        self.update_animation_juice()

        # 7. AI Behavior & Movement
        if not self.is_dragging:
            if self.state == PetState.IDLE:
                self.idle_counter += 1
                if self.idle_counter >= self.idle_target_time:
                    self.start_wandering()
            elif self.state == PetState.WALKING:
                self.move_towards_target()

        self.update()

    def update_animation_juice(self):
        """
        Calculates vertical bob, jump bounce, squash/stretch, and dynamic scaling
        using continuous sine waves and easing equations.
        """
        t = self.frame_count

        if self.state == PetState.IDLE:
            # Subtle breathing vertical bob (2-3px)
            self.target_scale = 1.0
            self.bounce_y = math.sin(t * 0.08) * 3.0
            self.squash_stretch_x = 1.0 + math.sin(t * 0.08) * 0.015
            self.squash_stretch_y = 1.0 - math.sin(t * 0.08) * 0.015

        elif self.state == PetState.WALKING:
            # Rhythmic, obvious vertical bobbing (paws taking strides)
            self.target_scale = 1.0
            self.bounce_y = abs(math.sin(t * 0.25)) * 8.0
            self.squash_stretch_x = 1.0 + math.sin(t * 0.5) * 0.03
            self.squash_stretch_y = 1.0 - math.sin(t * 0.5) * 0.03

        elif self.state == PetState.REACTING:
            # High, energetic jump triggered by hover or play
            jump_cycle = math.sin((40 - max(0, self.reaction_frames)) / 40.0 * math.pi)
            self.bounce_y = jump_cycle * 28.0
            stretch = (jump_cycle - 0.5) * 0.15
            self.squash_stretch_x = 1.0 - stretch
            self.squash_stretch_y = 1.0 + stretch
            self.target_scale = 1.1

        elif self.state == PetState.SATED:
            # Happy "pop" animation and gentle sway
            pop_ratio = max(0, self.pop_animation_frames) / 50.0
            pop_wave = math.sin(pop_ratio * math.pi * 3) * (pop_ratio * 0.2)
            self.target_scale = 1.0 + pop_wave
            self.bounce_y = abs(math.sin(t * 0.15)) * 5.0
            self.squash_stretch_x = 1.0
            self.squash_stretch_y = 1.0

        elif self.state == PetState.SLEEPING:
            # Sleeping: reduced scale, very slow deep breathing, no movement
            self.target_scale = 0.85
            self.bounce_y = math.sin(t * 0.04) * 1.5
            self.squash_stretch_x = 1.0 + math.sin(t * 0.04) * 0.02
            self.squash_stretch_y = 1.0 - math.sin(t * 0.04) * 0.02

        # Smooth dynamic scale easing
        self.scale_factor += (self.target_scale - self.scale_factor) * 0.12

    # -------------------------------------------------------------
    # AI Navigation & Wandering
    # -------------------------------------------------------------
    def start_wandering(self):
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 150
        min_x = max(20, screen.x() + margin)
        max_x = min(screen.width() - margin - 200, screen.x() + screen.width() - margin)
        min_y = max(20, screen.y() + margin)
        max_y = min(screen.height() - margin - 200, screen.y() + screen.height() - margin)

        if max_x <= min_x:
            max_x = min_x + 100
        if max_y <= min_y:
            max_y = min_y + 100

        self.target_pos = QPoint(
            random.randint(min_x, max_x),
            random.randint(min_y, max_y)
        )
        self.state = PetState.WALKING
        self.idle_counter = 0
        self.idle_target_time = random.randint(120, 260)

    def move_towards_target(self):
        curr_x, curr_y = self.x(), self.y()
        tar_x, tar_y = self.target_pos.x(), self.target_pos.y()
        dx = tar_x - curr_x
        dy = tar_y - curr_y
        dist = math.hypot(dx, dy)

        if dist < self.walk_speed * 2.0:
            self.state = PetState.IDLE
            self.move(tar_x, tar_y)
            return

        if dx > 1:
            self.facing_right = True
        elif dx < -1:
            self.facing_right = False

        step_x = int((dx / dist) * self.walk_speed)
        step_y = int((dy / dist) * self.walk_speed)
        self.move(curr_x + step_x, curr_y + step_y)

    def trigger_reaction(self):
        self.state = PetState.REACTING
        self.reaction_frames = 40
        self.bounce_y = 0

    # -------------------------------------------------------------
    # Painting & Rendering
    # -------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Retrieve sprite with pixel-perfect eye tracking baked in at 32x32 resolution
        sprite = self.animator.get_frame(
            self.state,
            self.frame_count,
            self.eye_shift_x,
            self.eye_shift_y
        )
        hitbox = self.get_hitbox()

        if sprite and not sprite.isNull():
            sw = hitbox.width()
            sh = hitbox.height()

            # Nearest-neighbor sharp 32x32 -> 128x128 pixel art scaling
            scaled = sprite.scaled(
                sw, sh,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

            # Horizontal sprite flipping: flips body and eyes in unison
            if not self.facing_right:
                scaled = scaled.transformed(QTransform().scale(-1, 1))

            # Draw the unified sprite at the exact hitbox position
            painter.drawPixmap(hitbox.x(), hitbox.y(), scaled)
        else:
            self.draw_fallback_cat(painter, hitbox)

    def draw_fallback_cat(self, painter: QPainter, hitbox: QRect):
        cat_color = QColor(255, 145, 30)
        painter.setBrush(cat_color)
        painter.setPen(Qt.PenStyle.NoPen)
        x, y, w, h = hitbox.x(), hitbox.y(), hitbox.width(), hitbox.height()
        painter.drawRoundedRect(x + int(w*0.2), y + int(h*0.3), int(w*0.6), int(h*0.5), 10, 10)
        painter.drawRoundedRect(x + int(w*0.25), y + int(h*0.15), int(w*0.5), int(h*0.35), 8, 8)

    # -------------------------------------------------------------
    # Mouse Interaction: Dragging, Hover, and Context Menu
    # -------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.get_hitbox().contains(event.position().toPoint()):
                self.is_dragging = True
                self.drag_offset = event.globalPosition().toPoint() - self.pos()
                self.trigger_reaction()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            new_pos = event.globalPosition().toPoint() - self.drag_offset
            self.move(new_pos)
            self.target_pos = new_pos
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.reaction_frames = 20
            self.idle_counter = 0
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ff911e;
                color: #000000;
            }
            QMenu::separator {
                height: 1px;
                background: #444444;
                margin: 4px 6px;
            }
        """)

        status_action = menu.addAction(f"Hunger: {self.hunger}%  |  Happiness: {self.happiness}%")
        status_action.setEnabled(False)
        menu.addSeparator()

        feed_action = menu.addAction("Feed 🍎")
        play_action = menu.addAction("Play 🧶")
        
        if self.state == PetState.SLEEPING:
            nap_action = menu.addAction("Wake Up ⏰")
        else:
            nap_action = menu.addAction("Nap 💤")

        menu.addSeparator()
        exit_action = menu.addAction("Exit ❌")

        action = menu.exec(event.globalPos())
        if action == feed_action:
            self.feed_pet()
        elif action == play_action:
            self.play_with_pet()
        elif action == nap_action:
            if self.state == PetState.SLEEPING:
                self.wake_up()
            else:
                self.make_pet_sleep()
        elif action == exit_action:
            QApplication.quit()

    # -------------------------------------------------------------
    # Needs System Actions
    # -------------------------------------------------------------
    def feed_pet(self):
        self.hunger = max(0, self.hunger - 25)
        self.happiness = min(100, self.happiness + 15)
        self.state = PetState.SATED
        self.pop_animation_frames = 50
        self.target_scale = 1.35
        print(f"Fed pet! Hunger: {self.hunger}%, Happiness: {self.happiness}%")

    def play_with_pet(self):
        self.happiness = min(100, self.happiness + 25)
        self.hunger = min(100, self.hunger + 5)
        self.trigger_reaction()
        self.reaction_frames = 50
        print(f"Played with pet! Happiness: {self.happiness}%, Hunger: {self.hunger}%")

    def make_pet_sleep(self):
        self.state = PetState.SLEEPING
        self.sleep_timer = 400
        self.target_scale = 0.85
        print("Pet is taking a nap... zzz")

    def wake_up(self):
        self.state = PetState.IDLE
        self.target_scale = 1.0
        self.idle_counter = 0
        print("Pet woke up!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = PetWindow()
    pet.show()
    sys.exit(app.exec())
