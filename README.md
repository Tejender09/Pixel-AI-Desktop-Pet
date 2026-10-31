# 🐾 Desktop Pet (PyQt6)

An interactive, animated Desktop Pet built with **PyQt6** that lives as a frameless, translucent overlay on your desktop. Features procedural sine-wave animations, real-time mouse eye-tracking locked to a 32x32 pixel grid, dynamic wandering AI, mouse dragging, and an interactive needs system.

---

## ✨ Features

- **Frameless & Stays-on-Top**: Translucent background (`WA_TranslucentBackground`) with clean alpha transparency and no window chrome.
- **Crisp Pixel Art Rendering**: Nearest-neighbor upscaling (`FastTransformation`) from 32×32 pixel art to 128×128 sharp resolution.
- **Direction-Aware Sprite Flipping**: Automatically flips horizontally based on movement direction.
- **Procedural Animation "Juice"**:
  - **IDLE**: Continuous subtle breathing bob and squash/stretch via sine waves.
  - **WALKING**: Rhythmic vertical stepping bob.
  - **REACTING**: High energetic parabolic jump arc when hovered or clicked.
  - **SATED**: Satisfied pop scale animation (`1.35x` elastic bounce) and blush/heart particles.
  - **SLEEPING**: Smooth scale-down to `0.85x`, calm resting breathing, and floating Zzz's.
- **Context-Aware Semantic Brain**:
  - Monitors the active window using native Windows APIs (`ctypes` / `pywin32`).
  - Reacts dynamically to your current workflow (e.g. gets `FOCUSED` when coding in VS Code, `CURIOUS` on browsers, `HAPPY` on Spotify).
- **Interactive Mouse Eye Tracking**:
  - The pet's eyes dynamically follow your cursor anywhere on the screen.
  - Pupils are stamped directly into the 32×32 sprite's eye sockets before scaling, ensuring 100% pixel-grid alignment with head bobbing, jumping, and body movement.
- **Mouse Drag & Drop**: Click and drag the pet to reposition it anywhere on your desktop.
- **Wandering AI**: Periodically wakes from idle, chooses screen-bounded destinations, and walks towards them.
- **Needs & Context Menu (Right-Click)**:
  - **Feed 🍎**: Decreases hunger, triggers happy SATED state and pop animation.
  - **Play 🧶**: Increases happiness and triggers an energetic reaction jump.
  - **Nap 💤 / Wake Up ⏰**: Puts the pet to sleep (reduced scale, stationary) or wakes it up.
  - **Live Status**: Displays current Hunger% and Happiness%.
  - **Exit ❌**: Safely closes the app.

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10+
- Git

### Install Dependencies
```bash
git clone https://github.com/Tejender09/desktop_pet.git
cd desktop_pet
pip install -r requirements.txt
```

---

## 🎮 Running the Pet

Launch the pet directly:
```bash
python src/main.py
```

### Controls & Interactions:
- **Hover**: Causes the pet to jump in surprise.
- **Left Click + Drag**: Pick up and move the pet around your screen.
- **Right Click**: Open the interaction context menu (Feed, Play, Nap, Status, Exit).

---

## 🧪 Testing

Run the automated test suite:
```bash
python tests/test_pet.py
python tests/test_eye_tracking.py
python tests/test_loop.py
```

---

## 📁 Project Structure

```
desktop_pet/
├── assets/
│   ├── config.json
│   └── sprites/          # 32x32 sprite sheets & frames (idle, walk, react, sated, sleep)
├── src/
│   ├── context_engine.py   # Active window & semantic OS context tracker
│   ├── generate_sprites.py # Procedural pixel art sprite generator
│   └── main.py             # Core PyQt6 Desktop Pet application & window
├── tests/
│   ├── test_context_engine.py # Context engine & active window tests
│   ├── test_pet.py         # Unit tests for pet state, window flags, needs, & hitbox
│   ├── test_eye_tracking.py# Pixel synchronization & head-bob eye tracking tests
│   └── test_loop.py        # Event loop and rendering lifecycle tests
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 📄 License
MIT License. Feel free to use and modify!

