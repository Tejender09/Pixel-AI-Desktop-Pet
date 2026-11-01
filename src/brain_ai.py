import os
import re
import time
import json
import threading
from typing import Callable, Optional

# Support both the current google-genai SDK and the deprecated google.generativeai
try:
    from google import genai as _genai_new
    _USE_NEW_SDK = True
except ImportError:
    _USE_NEW_SDK = False

if not _USE_NEW_SDK:
    try:
        import google.generativeai as _genai_old
    except ImportError:
        _genai_old = None


def load_gemini_api_key(config_dict: Optional[dict] = None) -> str:
    """
    Safely resolves the Gemini API key from multiple gitignored sources in priority order:
    1. user_data/secrets.json (recommended, gitignored)
    2. .env file in root directory (gitignored)
    3. os.environ["GEMINI_API_KEY"]
    4. config.json under api_keys.gemini
    """
    search_dirs = [os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), os.path.abspath(".")]

    # 1. user_data/secrets.json
    for base in search_dirs:
        secrets_path = os.path.join(base, "user_data", "secrets.json")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    key = data.get("gemini_api_key") or data.get("gemini")
                    if key and key.strip():
                        return key.strip()
            except Exception:
                pass

    # 2. .env file
    for base in search_dirs:
        env_path = os.path.join(base, ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            key = line.split("=", 1)[1].strip(" \"'")
                            if key:
                                return key
            except Exception:
                pass

    # 3. Environment Variable
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    # 4. Fallback to passed config_dict
    if config_dict:
        cfg_key = config_dict.get("api_keys", {}).get("gemini", "").strip()
        if cfg_key:
            return cfg_key

    return ""


class GeminiBrain:
    """
    Handles the LLM integration for the Desktop Pet using Google Gemini.
    Uses a background thread to prevent the main UI from freezing.
    Supports both google-genai (current) and google.generativeai (legacy).
    """
    def __init__(self, api_key: str, personality: str = "a tiny, sassy, and curious pixel-art pet"):
        self.api_key = api_key
        self.personality = personality
        self.is_thinking = False
        self.candidate_models = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash"]

        # Rate-limit guard: free tier = 5 req/min; stay safely under at 4/min
        self._rate_limit_per_minute: int = 4
        self._request_timestamps: list = []     # timestamps of recent API calls
        self._rate_limited_until: float = 0.0   # Unix timestamp of cooldown expiry

        if _USE_NEW_SDK:
            # Current SDK: google-genai
            self._client = _genai_new.Client(api_key=self.api_key)
            self._model_name = "gemini-2.5-flash"
            print("[AI] Using google-genai SDK with gemini-2.5-flash")
        elif _genai_old:
            # Legacy SDK: google.generativeai
            _genai_old.configure(api_key=self.api_key)
            self._legacy_model = None
            for model_name in self.candidate_models:
                try:
                    self._legacy_model = _genai_old.GenerativeModel(model_name)
                    print(f"[AI] Initialized Gemini model: {model_name}")
                    break
                except Exception:
                    continue
            if not self._legacy_model:
                self._legacy_model = _genai_old.GenerativeModel("gemini-2.5-flash")
        else:
            raise ImportError(
                "No Gemini SDK found. Install with: pip install google-genai"
            )

    def generate_reaction(self, subject: str, mood: str, callback: Callable[[str], None], fallback_callback: Optional[Callable[[], None]] = None):
        """
        Generates a reaction in a background thread to avoid UI freezing.
        :param subject: The content the pet is seeing (e.g. 'iPhone 16 Review')
        :param mood: The current pet state (e.g. 'WATCHING')
        :param callback: Function to call with the response string
        :param fallback_callback: Optional function to call if generation fails
        """
        if self.is_thinking:
            return

        # --- Rate-limit pre-check ---
        now = time.time()
        if now < self._rate_limited_until:
            remaining = int(self._rate_limited_until - now)
            print(f"[AI] Skipping (rate limited, {remaining}s cooldown left)")
            if fallback_callback:
                fallback_callback()
            return

        # Prune timestamps older than 60 seconds
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]
        if len(self._request_timestamps) >= self._rate_limit_per_minute:
            print(f"[AI] Skipping (hit {self._rate_limit_per_minute} req/min cap)")
            if fallback_callback:
                fallback_callback()
            return
        # Record this call
        self._request_timestamps.append(now)

        def _think():
            self.is_thinking = True
            try:
                print(f"[AI] Gemini observing screen: '{subject}' (Mood: {mood})...")
                prompt = (
                    f"You are Pixel, a witty, observant, and charming pixel-art desktop pet cat perched on the user's screen.\n"
                    f"The user has active window/content: '{subject}'. Current vibe: '{mood}'.\n"
                    f"Give ONE unique, clever, and spontaneous sentence commenting on what they are specifically doing or looking at.\n"
                    f"Rules:\n"
                    f"- DO NOT use emojis (the speech bubble uses a retro pixel font that cannot render emojis).\n"
                    f"- Keep it strictly under 14 words.\n"
                    f"- Never say 'You have been on' or 'Tell me more about it' or generic filler.\n"
                    f"- Be fun, a little sassy, or playfully curious like a real pet watching over their shoulder."
                )

                if _USE_NEW_SDK:
                    response = self._client.models.generate_content(
                        model=self._model_name,
                        contents=prompt
                    )
                    text = response.text.strip().replace('"', '')
                else:
                    response = self._legacy_model.generate_content(prompt)
                    text = response.text.strip().replace('"', '')

                print(f"[AI] Gemini spoke: \"{text}\"")
                callback(text)
            except Exception as e:
                err_str = str(e)
                print(f"[AI Error] {err_str}")
                if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                    # Parse retry_delay from the error message if present
                    match = re.search(r'retry.*?(\d+).*?second', err_str, re.IGNORECASE)
                    wait = int(match.group(1)) + 10 if match else 70
                    self._rate_limited_until = time.time() + wait
                    print(f"[AI] Rate limited by API. Cooling down for {wait}s.")
                if fallback_callback:
                    fallback_callback()
            finally:
                self.is_thinking = False

        thread = threading.Thread(target=_think, daemon=True)
        thread.start()
