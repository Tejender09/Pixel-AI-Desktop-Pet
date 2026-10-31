import os
import sys
from typing import Optional, Dict, Any

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


class ContextEngine:
    """
    The 'Brain' of the pet. Responsible for monitoring the operating system
    and active window to provide semantic context to the pet.
    Works natively on Windows via standard ctypes or pywin32/psutil.
    """
    def __init__(self):
        # Define how the pet should feel about certain apps
        # Format: "Process Name/Window Keyword": "Suggested State"
        self.app_moods = {
            "chrome.exe": "CURIOUS",
            "msedge.exe": "CURIOUS",
            "firefox.exe": "CURIOUS",
            "code.exe": "FOCUSED",
            "devenv.exe": "FOCUSED",
            "pycharm64.exe": "FOCUSED",
            "spotify.exe": "HAPPY",
            "discord.exe": "SOCIAL",
            "game": "EXCITED",
            "youtube": "CURIOUS"
        }
        self.last_window_title = ""
        self.last_process = ""

    def get_active_window_info(self) -> Dict[str, Any]:
        """
        Retrieves the title and process name of the currently focused window.
        Uses pywin32 if available, or native Windows ctypes fallback.
        """
        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                process_name = process.name().lower()
                return {
                    "title": title,
                    "process": process_name,
                    "hwnd": hwnd
                }
            except Exception as e:
                # Fall back to ctypes if pywin32 fails
                pass

        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    return {"title": "", "process": "", "hwnd": 0}

                # Get Window Title
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                else:
                    title = ""

                # Get Process ID
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                # Get Process Name
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

                return {
                    "title": title,
                    "process": process_name,
                    "hwnd": hwnd
                }
            except Exception as e:
                return {"title": "", "process": "", "hwnd": 0}

        return {"title": "", "process": "", "hwnd": 0}

    def analyze_context(self) -> Optional[str]:
        """
        Analyzes the active window and returns a 'mood' or 'interest'
        if a match is found in the app_moods dictionary.
        """
        info = self.get_active_window_info()
        title = info.get("title", "").lower()
        process = info.get("process", "")

        # Only trigger an update if the window actually changed to save CPU
        if title == self.last_window_title and process == self.last_process:
            return None

        self.last_window_title = title
        self.last_process = process

        # 1. Check process name first (more reliable)
        if process in self.app_moods:
            return self.app_moods[process]

        # 2. Check window title for keywords (more flexible)
        for keyword, mood in self.app_moods.items():
            if keyword in title:
                return mood

        return "NEUTRAL"
