import sys
import random
import math
import os
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QPoint, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor, QPixmap, QTransform, QCursor

# Import ContextEngine with fallback
try:
    from context_engine import ContextEngine
except ImportError:
    from src.context_engine import ContextEngine

# Import MemoryStore with fallback
try:
    from memory_store import MemoryStore
except ImportError:
    from src.memory_store import MemoryStore

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
    WATCHING = "WATCHING"  # Option A: Watching movies/videos with user
    WORRIED = "WORRIED"    # Option A: Nervous/anxious when errors/bugs occur
    GROOVING = "GROOVING"  # Option A: Dancing along with music/Spotify


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
            PetState.SLEEPING: [],
            PetState.WORRIED: [],
            PetState.WATCHING: [],
            PetState.GROOVING: []
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
            PetState.SLEEPING: ["sleep", "sleep_sheet.png"],
            PetState.WORRIED: ["worried", "worried_sheet.png"],
            PetState.WATCHING: ["watching", "watching_sheet.png"],
            PetState.GROOVING: ["grooving", "grooving_sheet.png"]
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
        img = base_pixmap.toImage()

        # Find eye socket pixels in upper portion of sprite (y < 22)
        eye_pixels = []
        for y in range(0, min(22, img.height())):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
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

            for py in range(min_y, max_y + 1):
                for px in range(min_x, max_x + 1):
                    if (px, py) in e:
                        img.setPixelColor(px, py, white_color)

            cx = (min_x + max_x) // 2
            cy = (min_y + max_y) // 2

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
            PetState.SLEEPING: 16,
            PetState.WORRIED: 6,
            PetState.WATCHING: 14,
            PetState.GROOVING: 7
        }
        speed = speed_map.get(state, 8)
        idx = (frame_count // speed) % len(frames)

        # In SLEEPING, SATED, and GROOVING states, eyes are styled lines (^.^, - -, ♪)
        if state in [PetState.SLEEPING, PetState.SATED, PetState.GROOVING]:
            return frames[idx]

        cache_key = (state, idx, shift_x, shift_y)
        if cache_key not in self.tracked_cache:
            self.tracked_cache[cache_key] = self._create_tracked_frame(frames[idx], shift_x, shift_y)
        return self.tracked_cache[cache_key]


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Frameless, stays-on-top, translucent background, fixed 200x200
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(200, 200)
        self.setMouseTracking(True)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        self.animator = AnimationManager(base_dir)

        # Position pet on screen
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
        self.last_mouse_pos = QCursor.pos()
        self.mouse_idle_ticks = 0

        # Reaction & Pop animation timers
        self.reaction_frames = 0
        self.pop_animation_frames = 0

        # Needs system: Hunger & Happiness
        self.hunger = 15      # 0 to 100
        self.happiness = 85   # 0 to 100
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

        # Cognition, Sight & Memory Engines
        self.brain = ContextEngine()
        self.memory = MemoryStore()
        self.current_context_mood = "NEUTRAL"

        # Heartbeat QTimer (30ms ~ 33 FPS)
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.update_logic)
        self.heartbeat.start(30)

    # -------------------------------------------------------------
    # Hitbox & Geometry
    # -------------------------------------------------------------
    def get_hitbox(self) -> QRect:
        sw = int(128 * self.scale_factor * self.squash_stretch_x)
        sh = int(128 * self.scale_factor * self.squash_stretch_y)
        x = (self.width() - sw) // 2
        y = (self.height() - sh) // 2 - int(self.bounce_y)
        return QRect(x, y, sw, sh)

    def get_grounded_hitbox(self) -> QRect:
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

        # 4. Memory Tracking & Active App Recording (every 1 second ~ 33 frames)
        if self.frame_count % 33 == 0:
            info = self.brain.get_active_window_info()
            proc = info.get("process", "")
            if proc:
                self.memory.record_app_time(proc, seconds=1)

        # Periodic memory auto-save (every ~60s)
        if self.frame_count % 1800 == 0:
            self.memory.save()

        # 5. Semantic Context & Mood Detection (sampled every ~0.6s)
        if self.frame_count % 20 == 0 and not self.is_dragging and self.state != PetState.SLEEPING:
            context_mood = self.brain.analyze_context()
            if context_mood:
                self.current_context_mood = context_mood
                print(f"🧠 Pet noticed context change: {context_mood}")

                # Behavioral Mapping (Option A)
                if context_mood == "WATCHING":
                    self.state = PetState.WATCHING
                elif context_mood == "WORRIED":
                    self.state = PetState.WORRIED
                elif context_mood == "GROOVING":
                    self.state = PetState.GROOVING
                elif context_mood == "FOCUSED":
                    self.walk_speed = 0.8
                elif context_mood == "CURIOUS":
                    self.trigger_reaction()
                elif context_mood == "NEUTRAL":
                    self.walk_speed = 2.0
                    if self.state in [PetState.WATCHING, PetState.WORRIED, PetState.GROOVING]:
                        self.state = PetState.IDLE

        # 6. Mouse Tracking & Window Gaze Sight (Option B)
        cursor_global = QCursor.pos()
        if cursor_global == self.last_mouse_pos:
            self.mouse_idle_ticks += 1
        else:
            self.mouse_idle_ticks = 0
            self.last_mouse_pos = cursor_global

        cursor_local = self.mapFromGlobal(cursor_global)
        hitbox = self.get_grounded_hitbox()
        face_center_x = hitbox.x() + hitbox.width() // 2
        face_center_y = hitbox.y() + int(hitbox.height() * 0.4)

        # If mouse is idle for > 2 seconds, pet gazes toward the center of the active window
        gaze_point = cursor_local
        if self.mouse_idle_ticks > 60:
            win_center = self.brain.get_window_center()
            if win_center:
                gaze_point = self.mapFromGlobal(QPoint(win_center[0], win_center[1]))

        dx = gaze_point.x() - face_center_x
        dy = gaze_point.y() - face_center_y

        screen_sx = -1 if dx < -25 else (1 if dx > 25 else 0)
        self.eye_shift_y = -1 if dy < -25 else (1 if dy > 25 else 0)
        self.eye_shift_x = screen_sx if self.facing_right else -screen_sx

        # 7. Hover Detection
        is_hovered = hitbox.contains(cursor_local)
        if is_hovered and not self.is_dragging:
            if self.state in [PetState.IDLE, PetState.WALKING, PetState.WATCHING, PetState.GROOVING]:
                self.trigger_reaction()

        # 8. Procedural Animation "Juice"
        self.update_animation_juice()

        # 9. Spatial AI & Wandering
        if not self.is_dragging:
            if self.state == PetState.IDLE:
                self.idle_counter += 1
                if self.idle_counter >= self.idle_target_time:
                    self.start_wandering()
            elif self.state == PetState.WALKING:
                self.move_towards_target()

        self.update()

    def update_animation_juice(self):
        t = self.frame_count

        if self.state == PetState.IDLE:
            self.target_scale = 1.0
            self.bounce_y = math.sin(t * 0.08) * 3.0
            self.squash_stretch_x = 1.0 + math.sin(t * 0.08) * 0.015
            self.squash_stretch_y = 1.0 - math.sin(t * 0.08) * 0.015

        elif self.state == PetState.WALKING:
            self.target_scale = 1.0
            self.bounce_y = abs(math.sin(t * 0.25)) * 8.0
            self.squash_stretch_x = 1.0 + math.sin(t * 0.5) * 0.03
            self.squash_stretch_y = 1.0 - math.sin(t * 0.5) * 0.03

        elif self.state == PetState.REACTING:
            jump_cycle = math.sin((40 - max(0, self.reaction_frames)) / 40.0 * math.pi)
            self.bounce_y = jump_cycle * 28.0
            stretch = (jump_cycle - 0.5) * 0.15
            self.squash_stretch_x = 1.0 - stretch
            self.squash_stretch_y = 1.0 + stretch
            self.target_scale = 1.1

        elif self.state == PetState.SATED:
            pop_ratio = max(0, self.pop_animation_frames) / 50.0
            pop_wave = math.sin(pop_ratio * math.pi * 3) * (pop_ratio * 0.2)
            self.target_scale = 1.0 + pop_wave
            self.bounce_y = abs(math.sin(t * 0.15)) * 5.0
            self.squash_stretch_x = 1.0
            self.squash_stretch_y = 1.0

        elif self.state == PetState.SLEEPING:
            self.target_scale = 0.85
            self.bounce_y = math.sin(t * 0.04) * 1.5
            self.squash_stretch_x = 1.0 + math.sin(t * 0.04) * 0.02
            self.squash_stretch_y = 1.0 - math.sin(t * 0.04) * 0.02

        elif self.state == PetState.WORRIED:
            # Anxious jitter and tense shivering
            self.target_scale = 0.95
            self.bounce_y = math.sin(t * 0.8) * 1.5
            self.squash_stretch_x = 1.0 + math.sin(t * 0.8) * 0.02
            self.squash_stretch_y = 1.0 - math.sin(t * 0.8) * 0.02

        elif self.state == PetState.WATCHING:
            # Relaxed sitting cinema companion
            self.target_scale = 1.02
            self.bounce_y = math.sin(t * 0.05) * 2.0
            self.squash_stretch_x = 1.0
            self.squash_stretch_y = 1.0

        elif self.state == PetState.GROOVING:
            # Energetic dance bobbing
            self.target_scale = 1.05
            self.bounce_y = abs(math.sin(t * 0.35)) * 10.0
            self.squash_stretch_x = 1.0 + math.sin(t * 0.35) * 0.04
            self.squash_stretch_y = 1.0 - math.sin(t * 0.35) * 0.04

        self.scale_factor += (self.target_scale - self.scale_factor) * 0.12

    # -------------------------------------------------------------
    # Spatial AI Navigation & Active Window Perching (Option B)
    # -------------------------------------------------------------
    def start_wandering(self):
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 70% chance to perch near the active user window if one is open
        perch_target = None
        if random.random() < 0.70:
            perch_target = self.brain.get_perch_target(
                screen.width(), screen.height(), self.width(), self.height()
            )

        if perch_target:
            self.target_pos = QPoint(perch_target[0], perch_target[1])
        else:
            # Fall back to free wandering within screen bounds
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
            # Return to context mood or IDLE upon arrival
            if self.current_context_mood in [PetState.WATCHING, PetState.WORRIED, PetState.GROOVING]:
                self.state = self.current_context_mood
            else:
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

            scaled = sprite.scaled(
                sw, sh,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

            if not self.facing_right:
                scaled = scaled.transformed(QTransform().scale(-1, 1))

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

        # Needs status header
        status_action = menu.addAction(f"Hunger: {self.hunger}%  |  Happiness: {self.happiness}%")
        status_action.setEnabled(False)

        # Bonding & Memory header (Option C)
        bond_action = menu.addAction(f"❤️ Bond: {self.memory.bond_level}%  |  ⭐ Fav: {self.memory.get_favorite_app()}")
        bond_action.setEnabled(False)
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
            self.close()

    # -------------------------------------------------------------
    # Needs System Actions
    # -------------------------------------------------------------
    def feed_pet(self):
        self.hunger = max(0, self.hunger - 25)
        self.happiness = min(100, self.happiness + 15)
        self.state = PetState.SATED
        self.pop_animation_frames = 50
        self.target_scale = 1.35
        self.memory.record_interaction("feed")
        print(f"Fed pet! Hunger: {self.hunger}%, Happiness: {self.happiness}%")

    def play_with_pet(self):
        self.happiness = min(100, self.happiness + 25)
        self.hunger = min(100, self.hunger + 5)
        self.trigger_reaction()
        self.reaction_frames = 50
        self.memory.record_interaction("play")
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

    def closeEvent(self, event):
        self.memory.save()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = PetWindow()
    pet.show()
    sys.exit(app.exec())
