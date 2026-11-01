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
    Handles the LLM integration for Pixel the Desktop Pet using Google Gemini.
    Features:
    - Multi-model fallback across separate free-tier quota pools.
    - Persistent rate-limit and cooldown tracking in user_data/ai_state.json.
    - Rolling 60s request throttle to respect free tier limits.
    - Seamless failover: if one model's daily quota is exhausted, auto-switches to the next.
    - Silent graceful fallback to dialogue templates when all models are cooling down.
    """
    def __init__(self, api_key: str, personality: str = "Pixel, a witty, observant, and sassy pixel-art cat who lives on the user's desktop"):
        self.api_key = api_key
        self.personality = personality
        self.is_thinking = False

        # Priority order: lightweight models with independent, generous quotas first
        self.candidate_models = [
            "gemini-2.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest",
            "gemini-2.5-flash"
        ]

        # Rate-limit guard: max 4 requests per minute across all models
        self._rate_limit_per_minute: int = 4
        self._request_timestamps: list = []

        # Model cooldown tracking: {model_name: cooldown_until_timestamp}
        self._model_cooldowns: dict[str, float] = {}
        self._state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_data", "ai_state.json"))
        self._load_state()

        if _USE_NEW_SDK:
            self._client = _genai_new.Client(api_key=self.api_key)
            print("[AI] Initialized with google-genai SDK.")
        elif _genai_old:
            _genai_old.configure(api_key=self.api_key)
            print("[AI] Initialized with google.generativeai SDK.")
        else:
            raise ImportError("No Gemini SDK found. Install with: pip install google-genai")

    def _load_state(self):
        """Loads model cooldown states from user_data/ai_state.json."""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    now = time.time()
                    self._model_cooldowns = {
                        k: v for k, v in data.get("cooldowns", {}).items()
                        if isinstance(v, (int, float)) and v > now
                    }
        except Exception:
            self._model_cooldowns = {}

    def _save_state(self):
        """Persists model cooldown states to user_data/ai_state.json."""
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            now = time.time()
            active_cooldowns = {k: v for k, v in self._model_cooldowns.items() if v > now}
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({"cooldowns": active_cooldowns}, f, indent=2)
        except Exception:
            pass

    def _parse_retry_delay(self, err_str: str) -> int:
        """
        Parses retry wait time in seconds from Gemini 429 errors.
        Handles protobuf 'seconds: 78311' or text '21h45m11s'.
        """
        # 1. Protobuf retry_delay field
        m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', err_str, re.DOTALL | re.IGNORECASE)
        if m:
            return int(m.group(1)) + 30

        # 2. Textual duration: Xh Ym Zs
        total = 0
        h = re.search(r'(\d+)h', err_str)
        mn = re.search(r'(\d+)m', err_str)
        s = re.search(r'(\d+(?:\.\d+)?)s', err_str)
        if h:
            total += int(h.group(1)) * 3600
        if mn:
            total += int(mn.group(1)) * 60
        if s:
            total += int(float(s.group(1)))
        if total > 0:
            return total + 30

        return 90

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Formats seconds into human readable duration."""
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        if hrs > 0:
            return f"{hrs}h {mins}m"
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    def _get_available_models(self) -> list[str]:
        """Returns candidate models that are not currently cooling down."""
        now = time.time()
        available = []
        for model in self.candidate_models:
            cooldown = self._model_cooldowns.get(model, 0.0)
            if now >= cooldown:
                available.append(model)
        return available

    def generate_reaction(self, subject: str, mood: str, callback: Callable[[str], None], fallback_callback: Optional[Callable[[], None]] = None):
        """
        Generates a reaction in a background thread to avoid UI freezing.
        Tries available models in order. If a model hits 429 quota, auto-switches to the next.
        """
        if self.is_thinking:
            return

        now = time.time()

        # Check rolling 1-minute rate limit
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60]
        if len(self._request_timestamps) >= self._rate_limit_per_minute:
            print(f"[AI] Throttled ({self._rate_limit_per_minute} req/min cap). Using dialogue.")
            if fallback_callback:
                fallback_callback()
            return

        available_models = self._get_available_models()
        if not available_models:
            min_wait = min(self._model_cooldowns.values()) - now if self._model_cooldowns else 60
            print(f"[AI] All models cooling down ({self._format_duration(max(1, int(min_wait)))} left). Using dialogue.")
            if fallback_callback:
                fallback_callback()
            return

        self._request_timestamps.append(now)

        def _think():
            self.is_thinking = True
            try:
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

                success = False
                models_to_try = self._get_available_models()

                for model_name in models_to_try:
                    try:
                        print(f"[AI] Pixel observing screen: '{subject}' (via {model_name})...")
                        if _USE_NEW_SDK:
                            response = self._client.models.generate_content(
                                model=model_name,
                                contents=prompt
                            )
                        else:
                            gen_model = _genai_old.GenerativeModel(model_name)
                            response = gen_model.generate_content(prompt)

                        text = response.text.strip().replace('"', '')
                        print(f"[AI] Pixel spoke: \"{text}\"")
                        callback(text)
                        success = True
                        break

                    except Exception as e:
                        err_str = str(e)
                        if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                            wait_sec = self._parse_retry_delay(err_str)
                            self._model_cooldowns[model_name] = time.time() + wait_sec
                            self._save_state()
                            dur_label = self._format_duration(wait_sec)
                            print(f"[AI] Model '{model_name}' hit quota limit (cooling down for {dur_label}).")
                            continue
                        else:
                            print(f"[AI] Error with {model_name}: {err_str[:120]}")
                            continue

                if not success and fallback_callback:
                    fallback_callback()

            finally:
                self.is_thinking = False

        thread = threading.Thread(target=_think, daemon=True)
        thread.start()
