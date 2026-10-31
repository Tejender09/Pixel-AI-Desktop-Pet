import os
import sys
from typing import Optional, Dict, Any, Tuple

# Try importing pywin32 and psutil, otherwise fall back to built-in ctypes
HAS_WIN32 = False
try:
    import win32gui
    import win32process
    import psutil
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long)
        ]


class ContextEngine:
    """
    The 'Brain' & 'Sight' of the pet. Responsible for monitoring the operating system,
    active window geometry, semantic context, and spatial positioning.
    Works natively on Windows via standard ctypes or pywin32/psutil.
    """
    def __init__(self):
        # Semantic keyword to mood/behavior mapping
        self.app_moods = {
            # Coding / Focused
            "code.exe": "FOCUSED",
            "devenv.exe": "FOCUSED",
            "pycharm64.exe": "FOCUSED",
            "sublime_text.exe": "FOCUSED",
            "notepad++.exe": "FOCUSED",
            # Music / Grooving
            "spotify.exe": "GROOVING",
            "music": "GROOVING",
            "soundcloud": "GROOVING",
            "apple music": "GROOVING",
            # Video / Cinema Watching
            "youtube": "WATCHING",
            "netflix": "WATCHING",
            "vlc.exe": "WATCHING",
            "disney": "WATCHING",
            "prime video": "WATCHING",
            "twitch": "WATCHING",
            # Errors / Worried
            "error": "WORRIED",
            "bug": "WORRIED",
            "traceback": "WORRIED",
            "exception": "WORRIED",
            "failed": "WORRIED",
            # Browsers / Curious
            "chrome.exe": "CURIOUS",
            "msedge.exe": "CURIOUS",
            "firefox.exe": "CURIOUS",
            "discord.exe": "SOCIAL"
        }
        self.last_window_title = ""
        self.last_process = ""

    def get_active_window_info(self) -> Dict[str, Any]:
        """
        Retrieves the title, process name, and geometry rect of the currently focused window.
        Uses pywin32 if available, or native Windows ctypes fallback.
        """
        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                process_name = process.name().lower()
                rect = win32gui.GetWindowRect(hwnd)
                return {
                    "title": title,
                    "process": process_name,
                    "hwnd": hwnd,
                    "rect": rect  # (left, top, right, bottom)
                }
            except Exception:
                pass

        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    return {"title": "", "process": "", "hwnd": 0, "rect": (0, 0, 0, 0)}

                # Window Title
                length = user32.GetWindowTextLengthW(hwnd)
                title = ""
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value

                # Process ID & Name
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process_name = ""
                if pid.value:
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                    if h_proc:
                        name_buf = ctypes.create_unicode_buffer(1024)
                        size = ctypes.c_ulong(1024)
                        if kernel32.QueryFullProcessImageNameW(h_proc, 0, name_buf, ctypes.byref(size)):
                            process_name = os.path.basename(name_buf.value).lower()
                        kernel32.CloseHandle(h_proc)

                # Window Rect
                r = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                rect = (r.left, r.top, r.right, r.bottom)

                return {
                    "title": title,
                    "process": process_name,
                    "hwnd": hwnd,
                    "rect": rect
                }
            except Exception:
                return {"title": "", "process": "", "hwnd": 0, "rect": (0, 0, 0, 0)}

        return {"title": "", "process": "", "hwnd": 0, "rect": (0, 0, 0, 0)}

    def get_perch_target(
        self,
        screen_w: int,
        screen_h: int,
        pet_w: int = 200,
        pet_h: int = 200
    ) -> Optional[Tuple[int, int]]:
        """
        Calculates spatial perch coordinates on or near the active window.
        Returns (x, y) target position on the screen, or None if no valid window.
        """
        info = self.get_active_window_info()
        rect = info.get("rect", (0, 0, 0, 0))
        left, top, right, bottom = rect
        win_w = right - left
        win_h = bottom - top

        # Ignore tiny or fullscreen-covering windows (like Windows desktop itself)
        if win_w < 150 or win_h < 150 or (win_w >= screen_w and win_h >= screen_h):
            return None

        # Perch on the window titlebar / header:
        # Paws resting on top edge of window
        target_x = left + (win_w - pet_w) // 2
        target_y = top - pet_h + 50

        # If too high off screen, sit in the top-right corner of the window instead
        if target_y < 10:
            target_y = top + 20
            target_x = min(right - pet_w + 20, screen_w - pet_w)

        # Clamp strictly within screen bounds
        clamped_x = max(10, min(screen_w - pet_w - 10, target_x))
        clamped_y = max(10, min(screen_h - pet_h - 10, target_y))
        return (clamped_x, clamped_y)

    def get_window_center(self) -> Optional[Tuple[int, int]]:
        """
        Returns global screen coordinates of the active window center
        for natural companion gaze / sight tracking.
        """
        info = self.get_active_window_info()
        rect = info.get("rect", (0, 0, 0, 0))
        left, top, right, bottom = rect
        if right > left and bottom > top:
            return ((left + right) // 2, (top + bottom) // 2)
        return None

    def analyze_context(self) -> Optional[str]:
        """
        Analyzes the active window and returns a semantic 'mood'
        if a match is found in the app_moods dictionary.
        """
        info = self.get_active_window_info()
        title = info.get("title", "").lower()
        process = info.get("process", "")

        # Only trigger an update if the window actually changed
        if title == self.last_window_title and process == self.last_process:
            return None

        self.last_window_title = title
        self.last_process = process

        # 1. Check title keywords first for priority (e.g. YouTube in Chrome, Error in IDE)
        for keyword, mood in self.app_moods.items():
            if not keyword.endswith(".exe") and keyword in title:
                return mood

        # 2. Check process name
        if process in self.app_moods:
            return self.app_moods[process]

        return "NEUTRAL"
