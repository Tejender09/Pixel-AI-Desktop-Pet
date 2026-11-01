import sys
import random
import math
import os
import json
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer, QRect, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPixmap, QTransform, QCursor, QFont, QFontMetrics, QPolygonF

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


class SpeechBubbleWidget(QWidget):
    """
    A dedicated, frameless, translucent speech bubble overlay that floats
    above the pet in global screen coordinates. Eliminates window-border clipping,
    features a seamless triangular pointer tail, soft multi-layer drop shadow,
    crisp antialiased typography, pop-in spring easing, and smooth fade-out.
    """
    def __init__(self, pet_window):
        super().__init__()
        self.pet = pet_window

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.text = ""
        self.opacity = 0.0
        self.scale = 0.8
        self.visible_ticks = 0
        self.total_ticks = 0
        self.anim_tick = 0
        self.bubble_w = 120
        self.bubble_h = 38
        self.hide()

    def show_speech(self, text: str, duration_ticks: int = 150):
        if not text:
            self.hide()
            return

        self.text = text
        self.total_ticks = max(60, duration_ticks)
        self.visible_ticks = self.total_ticks
        self.anim_tick = 0
        self.opacity = 0.0

        # Calculate dimensions from font metrics with max-width word wrap
        font_size = self.pet.config.get("visuals", {}).get("bubble_font_size", 10)
        font = QFont("Consolas", font_size, QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.Monospace)
        metrics = QFontMetrics(font)

        # Max bubble content width (in pixels) before we wrap
        MAX_TEXT_W = 220
        pad_x = 14
        pad_y = 10

        raw_text_w = metrics.horizontalAdvance(text)
        if raw_text_w <= MAX_TEXT_W:
            # Single line - fits fine
            self.bubble_w = max(90, raw_text_w + pad_x * 2)
            self.bubble_h = max(36, metrics.height() + pad_y * 2)
        else:
            # Multi-line: measure bounding box with word wrap
            self.bubble_w = MAX_TEXT_W + pad_x * 2
            bound = metrics.boundingRect(
                QRect(0, 0, MAX_TEXT_W, 2000),
                int(Qt.AlignmentFlag.AlignLeft) | int(Qt.TextFlag.TextWordWrap),
                text
            )
            self.bubble_h = max(36, bound.height() + pad_y * 2)

        # Canvas includes padding for shadow (8px each side) + tail space (10px)
        # We add extra height for the tail regardless of direction —
        # update_position decides which side it goes, paintEvent uses _tail_above flag
        TAIL_EXTRA = 12
        canvas_w = int(self.bubble_w + 24)
        canvas_h = int(self.bubble_h + 24 + TAIL_EXTRA)
        self.resize(canvas_w, canvas_h)

        self.update_position()
        self.show()
        self.update()

    def update_position(self):
        if not self.isVisible():
            return
        screen = QApplication.primaryScreen().availableGeometry()

        # Horizontally centered over pet
        bx = self.pet.x() + (self.pet.width() - self.width()) // 2
        # Try to place bubble ABOVE the pet
        by_above = self.pet.y() - self.height() + 16

        # If too close to top edge, place BELOW the pet instead
        if by_above < screen.y() + 8:
            by = self.pet.y() + self.pet.height() + 4
            self._tail_above = False   # tail points UP (from bottom of bubble toward pet above)
        else:
            by = by_above
            self._tail_above = True    # tail points DOWN (from bottom of bubble toward pet below)

        clamped_x = max(screen.x() + 8, min(screen.x() + screen.width() - self.width() - 8, bx))
        clamped_y = max(screen.y() + 8, min(screen.y() + screen.height() - self.height() - 8, by))

        # Track pet center in local bubble coords so tail always points at the pet
        pet_center_x_global = self.pet.x() + self.pet.width() // 2
        self._pet_offset_x = pet_center_x_global - clamped_x

        self.move(clamped_x, clamped_y)

    def tick(self):
        if self.visible_ticks <= 0:
            if self.isVisible():
                self.hide()
            return

        self.anim_tick += 1
        self.visible_ticks -= 1

        # Pop-in spring easing over first 10 frames
        if self.anim_tick <= 6:
            self.scale = 0.70 + (self.anim_tick / 6.0) * 0.35
            self.opacity = min(1.0, self.anim_tick / 4.0)
        elif self.anim_tick <= 10:
            self.scale = 1.05 - ((self.anim_tick - 6) / 4.0) * 0.05
            self.opacity = 1.0
        else:
            self.scale = 1.0
            # Fade-out over the final 16 frames
            if self.visible_ticks < 16:
                self.opacity = max(0.0, self.visible_ticks / 16.0)
            else:
                self.opacity = 1.0

        self.update_position()
        self.update()

    def paintEvent(self, event):
        if not self.text or self.opacity <= 0.01:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setOpacity(self.opacity)

        # Chunky pixel art unit: 2 screen pixels per retro pixel block
        P = 2
        TAIL_H = 4 * P   # height of the 4-step pixel tail

        # Floating drift snapped to pixel grid
        float_y = int(math.sin(self.anim_tick * 0.1) * 2.0)

        # Is the bubble above (tail down) or below (tail up) the pet?
        tail_above = getattr(self, '_tail_above', True)

        # Scale anchor at the edge closest to the pet
        cx = self.width() // 2
        scale_anchor_y = (self.height() - 8) if tail_above else 8
        painter.translate(cx, scale_anchor_y)
        painter.scale(self.scale, self.scale)
        painter.translate(-cx, -scale_anchor_y)

        # Geometry — leave room for tail on the correct side
        margin_x = 12
        if tail_above:
            # Tail hangs below the box
            bx = margin_x
            by = 6 + float_y
        else:
            # Tail pokes above the box
            bx = margin_x
            by = TAIL_H + 6 + float_y

        bw = ((self.width() - margin_x * 2) // P) * P
        bh = (self.bubble_h // P) * P

        # Tail X: track actual pet center in local coords, clamped inside box
        pet_offset = getattr(self, '_pet_offset_x', self.width() // 2)
        pet_offset = max(bx + 4 * P, min(bx + bw - 4 * P, pet_offset))
        tail_cx = (pet_offset // P) * P

        border_hex = self.pet.config.get("visuals", {}).get("bubble_border_color", "#1A1C23")
        border_c = QColor(border_hex)
        bg_hex = self.pet.config.get("visuals", {}).get("bubble_color", "#FFFFFF")
        bg_c = QColor(bg_hex)
        shadow_c = QColor(0, 0, 0, 80)

        tx_rel = tail_cx - bx   # tail center relative to box left

        def draw_box_body(p, ox, oy, w, h):
            """Stepped pixel corners for the main balloon box."""
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(ox,           oy + 2 * P, w,         h - 4 * P)
            p.drawRect(ox + P,       oy + P,     w - 2 * P, h - 2 * P)
            p.drawRect(ox + 2 * P,   oy,         w - 4 * P, h)

        def draw_tail_down(p, ox, oy, w, h):
            """4-step descending pixel tail at bottom of box."""
            tx = ox + tx_rel
            ty = oy + h
            p.drawRect(tx - 3 * P, ty,           7 * P, P)
            p.drawRect(tx - 2 * P, ty + P,       5 * P, P)
            p.drawRect(tx - 1 * P, ty + 2 * P,   3 * P, P)
            p.drawRect(tx,         ty + 3 * P,   P,     P)

        def draw_tail_up(p, ox, oy, w, h):
            """4-step ascending pixel tail at top of box (bubble is below pet)."""
            tx = ox + tx_rel
            ty = oy
            p.drawRect(tx,         ty - 4 * P, P,     P)
            p.drawRect(tx - P,     ty - 3 * P, 3 * P, P)
            p.drawRect(tx - 2 * P, ty - 2 * P, 5 * P, P)
            p.drawRect(tx - 3 * P, ty - P,     7 * P, P)

        draw_tail = draw_tail_down if tail_above else draw_tail_up

        def draw_silhouette(p, ox, oy, fill):
            p.setBrush(fill)
            draw_box_body(p, ox, oy, bw, bh)
            draw_tail(p, ox, oy, bw, bh)

        # 1. Shadow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_c)
        draw_silhouette(painter, bx + 2 * P, by + 2 * P, shadow_c)

        # 2. Outer border
        painter.setBrush(border_c)
        draw_silhouette(painter, bx, by, border_c)

        # 3. Inner fill (inset by 1 pixel block)
        ibw = bw - 2 * P
        ibh = bh - 2 * P
        ibx = bx + P
        iby = by + P

        painter.setBrush(bg_c)
        draw_box_body(painter, ibx, iby, ibw, ibh)

        # Inner tail (1 step shorter to reveal the border ring)
        itx = tail_cx - bx   # reuse relative offset
        if tail_above:
            ty = iby + ibh
            painter.drawRect(ibx + itx - 2 * P, ty - P,       5 * P, 2 * P)
            painter.drawRect(ibx + itx - 1 * P, ty + P,       3 * P, P)
            painter.drawRect(ibx + itx,          ty + 2 * P,  P,     P)
        else:
            ty = iby
            painter.drawRect(ibx + itx,          ty - 3 * P, P,     P)
            painter.drawRect(ibx + itx - 1 * P,  ty - 2 * P, 3 * P, P)
            painter.drawRect(ibx + itx - 2 * P,  ty - P,     5 * P, 2 * P)

        # 4. Pixelated Typography
        font_size = self.pet.config.get("visuals", {}).get("bubble_font_size", 10)
        font = QFont("Consolas", font_size, QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        painter.setFont(font)

        text_hex = self.pet.config.get("visuals", {}).get("bubble_text_color", "#1A1C23")
        painter.setPen(QColor(text_hex))

        inner_pad = 10
        text_rect = QRect(bx + inner_pad, by + inner_pad, bw - inner_pad * 2, bh - inner_pad * 2)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
            self.text
        )


class AnimationManager:
    """
    Loads and manages animated sprites for all pet states.
    Supports single spritesheets (e.g. 128x32 horizontal strip)
    as well as individual 32x32 frame sequences (e.g. 01.png, 02.png).
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
        self.tracked_cache = {}
        self.load_assets()

    def load_assets(self):
        sprites_dir = os.path.join(self.base_path, "sprites")
        
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

        eye_pixels = []
        for y in range(0, min(22, img.height())):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if (c.red() > 240 and c.green() > 240 and c.blue() > 240) or \
                   (c.red() < 60 and c.green() < 60 and c.blue() < 60 and c.alpha() > 200):
                    eye_pixels.append((x, y))

        if not eye_pixels:
            return base_pixmap

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

        # Configuration & Speech
        self.load_config()
        self.speech_text = ""
        self.speech_timer = 0
        self.speech_duration = 0
        self.bubble_widget = SpeechBubbleWidget(self)

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
    # Configuration & Dialogue
    # -------------------------------------------------------------
    def load_config(self):
        """Loads pet personality and settings from config.json."""
        try:
            config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "config.json"))
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Config Error: {e}")
            self.config = {}

    def say(self, text: str, duration: int = 150):
        """Displays text in the speech bubble above the pet."""
        self.speech_text = text
        self.speech_duration = duration
        self.speech_timer = duration
        self.bubble_widget.show_speech(text, duration)

    def trigger_context_comment(self):
        """
        Extracts the subject of the active window and generates a
        dynamic comment based on the content.
        """
        subject = self.brain.get_content_subject()
        if not subject:
            return

        subject_lower = subject.lower()

        # Semantic Comment Mapping
        # (Keyword in subject -> List of possible comments)
        comment_map = {
            "review": [
                f"A {subject} review? Is it any good?",
                f"Hmm, I wonder if {subject} is actually worth it...",
                f"I bet I could do a better review of {subject}!"
            ],
            "tutorial": [
                f"Wow, learning about {subject}! You're getting so smart!",
                f"I'm taking notes on this {subject} tutorial too!",
                f"Look at you go! Master of {subject}!"
            ],
            "gameplay": [
                f"{subject} looks fun! Can I have a turn?",
                f"Ooh, {subject}! I bet I could beat that high score!",
                f"Gaming time! I'll be your cheerleader for {subject}!"
            ],
            "music": [
                f"This {subject} sounds amazing!",
                f"Bop it! I love this {subject} vibe!",
                f"Can you turn up the {subject}? I want to dance!"
            ],
            "coding": [
                f"Working on {subject}? Don't forget the semicolons!",
                f"Looking at {subject}... looks like a lot of bugs to me! Hehe!",
                f"I'm helping you with {subject} just by looking at it!"
            ],
            "news": [
                f"What's happening with {subject} now?",
                f"The world is crazy, huh? {subject} is wild!",
                f"I prefer my news in treats, not {subject}!"
            ]
        }

        # Find a match
        chosen_comment = None
        for keyword, comments in comment_map.items():
            if keyword in subject_lower:
                chosen_comment = random.choice(comments)
                break

        # Generic fallback if no keyword matches but we have a subject
        if not chosen_comment:
            generic = [
                f"What's this {subject} thing?",
                f"Oh! {subject}! Tell me more about it!",
                f"I've never heard of {subject}, is it tasty?",
                f"You've been looking at {subject} for a while now!"
            ]
            chosen_comment = random.choice(generic)

        self.say(chosen_comment, duration=250)

    # -------------------------------------------------------------
    # Main Heartbeat Update Loop
    # -------------------------------------------------------------
    def update_logic(self):
        self.frame_count += 1

        # 1. Needs System Tick
        if self.frame_count % 2000 == 0:
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

        # 4. Memory Tracking & Active App Recording (every ~1s)
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
                print(f"[Brain] Pet noticed context change: {context_mood}")

                # 35% chance to comment on the NEW content specifically
                if random.random() < 0.35:
                    self.trigger_context_comment()

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

        # If mouse is idle for > 2 seconds, pet gazes toward active window center
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

        # 8.5 Speech Bubble Tick
        self.bubble_widget.tick()
        if self.speech_timer > 0:
            self.speech_timer -= 1
            if self.speech_timer <= 0:
                self.speech_text = ""

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
            self.target_scale = 0.95
            self.bounce_y = math.sin(t * 0.8) * 1.5
            self.squash_stretch_x = 1.0 + math.sin(t * 0.8) * 0.02
            self.squash_stretch_y = 1.0 - math.sin(t * 0.8) * 0.02

        elif self.state == PetState.WATCHING:
            self.target_scale = 1.02
            self.bounce_y = math.sin(t * 0.05) * 2.0
            self.squash_stretch_x = 1.0
            self.squash_stretch_y = 1.0

        elif self.state == PetState.GROOVING:
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
        
        perch_target = None
        if random.random() < 0.70:
            perch_target = self.brain.get_perch_target(
                screen.width(), screen.height(), self.width(), self.height()
            )

        if perch_target:
            self.target_pos = QPoint(perch_target[0], perch_target[1])
        else:
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
            if self.current_context_mood in [PetState.WATCHING, PetState.WORRIED, PetState.GROOVING]:
                self.state = self.current_context_mood
            else:
                self.state = PetState.IDLE
            self.move(tar_x, tar_y)
            self.bubble_widget.update_position()
            return

        if dx > 1:
            self.facing_right = True
        elif dx < -1:
            self.facing_right = False

        step_x = int((dx / dist) * self.walk_speed)
        step_y = int((dy / dist) * self.walk_speed)
        self.move(curr_x + step_x, curr_y + step_y)
        self.bubble_widget.update_position()

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

    def draw_speech_bubble(self, painter: QPainter, hitbox: QRect):
        """
        In-canvas speech bubble drawing fallback with blocky pixel art geometry,
        pixel drop shadow, crisp typography, and seamless pointed tail.
        """
        if not self.speech_text:
            return

        text = self.speech_text
        font_size = self.config.get("visuals", {}).get("bubble_font_size", 10)
        font = QFont("Consolas", font_size, QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.Monospace)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()

        padding = 12
        bw = min(float(self.width() - 16), float(text_w + padding * 2))
        bh = float(text_h + padding * 2)

        bx = float((self.width() - int(bw)) // 2)
        by = float(max(4, hitbox.y() - int(bh) - 8))

        P = 2
        x = int(bx)
        y = int(by)
        bw_i = int(bw // P * P)
        bh_i = int(bh // P * P)
        tail_cx = int(x + (bw_i * 0.38 if not self.facing_right else bw_i * 0.62))

        border_c = QColor(self.config.get("visuals", {}).get("bubble_border_color", "#1A1C23"))
        bg_c = QColor(self.config.get("visuals", {}).get("bubble_color", "#FFFFFF"))
        shadow_c = QColor(0, 0, 0, 75)

        def draw_pixel_silhouette(p, ox, oy, fill_color):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill_color)
            p.drawRect(ox, oy + 2 * P, bw_i, bh_i - 4 * P)
            p.drawRect(ox + P, oy + P, bw_i - 2 * P, bh_i - 2 * P)
            p.drawRect(ox + 2 * P, oy, bw_i - 4 * P, bh_i)
            tx = ox + (tail_cx - x)
            ty = oy + bh_i
            p.drawRect(tx - 3 * P, ty, 7 * P, P)
            p.drawRect(tx - 2 * P, ty + P, 5 * P, P)
            p.drawRect(tx - 1 * P, ty + 2 * P, 3 * P, P)
            p.drawRect(tx, ty + 3 * P, P, P)

        # 1. Shadow
        draw_pixel_silhouette(painter, x + 2 * P, y + 2 * P, shadow_c)

        # 2. Border
        draw_pixel_silhouette(painter, x, y, border_c)

        # 3. Inner Fill
        ibx = x + P
        iby = y + P
        ibw = bw_i - 2 * P
        ibh = bh_i - 2 * P
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_c)
        painter.drawRect(ibx, iby + 2 * P, ibw, ibh - 4 * P)
        painter.drawRect(ibx + P, iby + P, ibw - 2 * P, ibh - 2 * P)
        painter.drawRect(ibx + 2 * P, iby, ibw - 4 * P, ibh)
        tx = tail_cx
        ty = y + bh_i
        painter.drawRect(tx - 2 * P, ty - P, 5 * P, 2 * P)
        painter.drawRect(tx - 1 * P, ty + P, 3 * P, P)
        painter.drawRect(tx, ty + 2 * P, P, P)

        # 4. Text
        font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        painter.setFont(font)
        text_hex = self.config.get("visuals", {}).get("bubble_text_color", "#1A1C23")
        painter.setPen(QColor(text_hex))
        painter.drawText(QRect(x, y, bw_i, bh_i), Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

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
            self.bubble_widget.update_position()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.reaction_frames = 20
            self.idle_counter = 0
            self.bubble_widget.update_position()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, 'bubble_widget'):
            self.bubble_widget.update_position()

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
        bond_action = menu.addAction(f"Bond: {self.memory.bond_level}%  |  Fav: {self.memory.get_favorite_app()}")
        bond_action.setEnabled(False)
        menu.addSeparator()

        feed_action = menu.addAction("Feed [Apple]")
        play_action = menu.addAction("Play [Ball]")

        if self.state == PetState.SLEEPING:
            nap_action = menu.addAction("Wake Up [Alarm]")
        else:
            nap_action = menu.addAction("Nap [Zzz]")

        menu.addSeparator()
        exit_action = menu.addAction("Exit [X]")

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
    def trigger_speech(self, event_key: str):
        """
        Picks a random dialogue line from config.json for the given event key
        (e.g. 'FEED', 'PLAY', 'NAP', 'WAKE') and displays it as a speech bubble.
        """
        dialogues = self.config.get("dialogues", {})
        lines = dialogues.get(event_key, [])
        if not lines:
            # Fallback defaults if config is missing
            defaults = {
                "FEED": ["Yummy! Thanks!"],
                "PLAY": ["Wheee! Let's go!"],
                "NAP": ["Yawn... sleepy..."],
                "WAKE": ["I'm awake! I'm awake!"],
            }
            lines = defaults.get(event_key, [])
        if lines:
            self.say(random.choice(lines), duration=160)

    def feed_pet(self):
        self.hunger = max(0, self.hunger - 25)
        self.happiness = min(100, self.happiness + 15)
        self.state = PetState.SATED
        self.pop_animation_frames = 50
        self.target_scale = 1.35
        self.memory.record_interaction("feed")
        self.trigger_speech("FEED")
        print(f"Fed pet! Hunger: {self.hunger}%, Happiness: {self.happiness}%")

    def play_with_pet(self):
        self.happiness = min(100, self.happiness + 25)
        self.hunger = min(100, self.hunger + 5)
        self.trigger_reaction()
        self.reaction_frames = 50
        self.memory.record_interaction("play")
        self.trigger_speech("PLAY")
        print(f"Played with pet! Happiness: {self.happiness}%, Hunger: {self.hunger}%")

    def make_pet_sleep(self):
        self.state = PetState.SLEEPING
        self.sleep_timer = 400
        self.target_scale = 0.85
        self.trigger_speech("NAP")
        print("Pet is taking a nap... zzz")

    def wake_up(self):
        self.state = PetState.IDLE
        self.target_scale = 1.0
        self.idle_counter = 0
        self.trigger_speech("WAKE")
        print("Pet woke up!")

    def closeEvent(self, event):
        if hasattr(self, 'bubble_widget'):
            self.bubble_widget.close()
        self.memory.save()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = PetWindow()
    pet.show()
    sys.exit(app.exec())
