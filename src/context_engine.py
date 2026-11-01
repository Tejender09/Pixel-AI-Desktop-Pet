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
            "github": "FOCUSED",
            "stackoverflow": "FOCUSED",
            "vscode": "FOCUSED",
            # Music / Grooving (Strictly when audio is playing)
            "spotify.exe": "GROOVING",
            "youtube music": "GROOVING",
            "apple music": "GROOVING",
            "soundcloud": "GROOVING",
            "music": "GROOVING",
            "song": "GROOVING",
            "songs": "GROOVING",
            "concert": "GROOVING",
            "remix": "GROOVING",
            "lofi": "GROOVING",
            "beats": "GROOVING",
            "soundtrack": "GROOVING",
            "official audio": "GROOVING",
            "music video": "GROOVING",
            # Video / Cinema Watching (Normal videos, tutorials, movies, streams)
            "youtube": "WATCHING",
            "netflix": "WATCHING",
            "vlc.exe": "WATCHING",
            "disney": "WATCHING",
            "prime video": "WATCHING",
            "twitch": "WATCHING",
            "movie": "WATCHING",
            "cinema": "WATCHING",
            "tutorial": "WATCHING",
            "podcast": "WATCHING",
            # Errors / Worried
            "error": "WORRIED",
            "bug": "WORRIED",
            "traceback": "WORRIED",
            "exception": "WORRIED",
            "failed": "WORRIED",
            # Browsers / Curious (Fallback)
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
        pet_h: int = 200,
        current_mood: str = "NEUTRAL"
    ) -> Optional[Tuple[int, int]]:
        """
        Calculates a random perch coordinate along the edges of the active window.
        If current_mood is WATCHING or FOCUSED, it avoids the window entirely
        to prevent blocking content.
        """
        import random
        info = self.get_active_window_info()
        rect = info.get("rect", (0, 0, 0, 0))
        left, top, right, bottom = rect
        win_w = right - left
        win_h = bottom - top

        if win_w < 150 or win_h < 150 or (win_w >= screen_w and win_h >= screen_h):
            return None

        # AI STEALTH MODE: If we are watching or focusing, do NOT perch on the window
        if current_mood in ["WATCHING", "FOCUSED"]:
            return None

        # Randomly choose which edge to perch on: 0=Top, 1=Left, 2=Right
        edge = random.randint(0, 2)

        if edge == 0: # Top Edge
            target_x = random.randint(left, max(left, right - pet_w))
            target_y = top - pet_h + 20
        elif edge == 1: # Left Edge
            target_x = left - pet_w + 20
            target_y = random.randint(top, max(top, bottom - pet_h))
        else: # Right Edge
            target_x = right - 20
            target_y = random.randint(top, max(top, bottom - pet_h))

        clamped_x = max(10, min(screen_w - pet_w - 10, target_x))
        clamped_y = max(10, min(screen_h - pet_h - 10, target_y))
        return (clamped_x, clamped_y)

    def get_window_center(self) -> Optional[Tuple[int, int]]:
        """
        Returns the screen-space (x, y) center of the currently active window,
        or None if the window geometry is unavailable or invalid.
        Used by the pet for gaze tracking when the mouse is idle.
        """
        info = self.get_active_window_info()
        rect = info.get("rect", (0, 0, 0, 0))
        left, top, right, bottom = rect
        w = right - left
        h = bottom - top
        if w < 50 or h < 50:
            return None
        cx = left + w // 2
        cy = top + h // 2
        return (cx, cy)

    def get_content_subject(self) -> str:
        """
        Extracts the actual subject from the active window title by stripping
        common browser and platform suffixes.
        """
        info = self.get_active_window_info()
        title = info.get("title", "")
        if not title:
            return ""

        # Common suffixes to strip
        suffixes = [
            " - YouTube", " - Mozilla Firefox", " - Google Chrome",
            " - Microsoft Edge", " - Netflix", " - Twitch",
            " - Spotify", " - Discord", " - VS Code", " - Visual Studio Code"
        ]

        subject = title
        for s in suffixes:
            if subject.endswith(s):
                subject = subject.replace(s, "")
                break

        # Also strip common separators at the end
        subject = subject.strip(" - |")
        return subject

    def is_audio_playing(self) -> bool:
        """
        Detects if Windows is actively outputting sound to speakers or headphones.
        Inspects active audio sessions and peak volume via Windows Core Audio.
        Returns True if sound is actively playing, False if muted/paused/silent.
        """
        try:
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                # State 1 = Active audio session
                if getattr(s, 'State', 0) == 1:
                    try:
                        meter = s._ctl.QueryInterface(IAudioMeterInformation)
                        if meter.GetPeakValue() > 0.0005:
                            return True
                    except Exception:
                        return True
            return False
        except Exception:
            return False

    def analyze_context(self) -> Optional[str]:
        """
        Analyzes the active window and returns a semantic 'mood'
        if a match is found in the app_moods dictionary.
        Incorporates real-time audio detection so the pet only grooves
        when audio is actively playing through speakers.
        """
        info = self.get_active_window_info()
        title = info.get("title", "").lower()
        process = info.get("process", "").lower()

        # Only trigger an update if the window actually changed
        if title == self.last_window_title and process == self.last_process:
            return None

        self.last_window_title = title
        self.last_process = process

        # 1. PRIORITY: Check title keywords first.
        # This handles YouTube/Netflix/etc inside Firefox/Chrome.
        for keyword, mood in self.app_moods.items():
            # If it's a keyword (not a .exe), check if it's in the window title
            if not keyword.endswith(".exe") and keyword in title:
                if mood == "GROOVING":
                    # Only groove if audio is literally playing through speakers!
                    if self.is_audio_playing():
                        return "GROOVING"
                    else:
                        return "WATCHING" if ("youtube" in title or "video" in title) else "IDLE"
                return mood

        # 2. FALLBACK: Check process name.
        if process in self.app_moods:
            mood = self.app_moods[process]
            if mood == "GROOVING":
                if self.is_audio_playing():
                    return "GROOVING"
                else:
                    return "IDLE"
            return mood

        return "NEUTRAL"
