import threading
from typing import Callable

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

        if _USE_NEW_SDK:
            # Current SDK: google-genai
            self._client = _genai_new.Client(api_key=self.api_key)
            self._model_name = "gemini-2.0-flash"
            print("[AI] Using current google-genai SDK with gemini-2.0-flash")
        elif _genai_old:
            # Legacy SDK: google.generativeai
            _genai_old.configure(api_key=self.api_key)
            self._legacy_model = _genai_old.GenerativeModel("gemini-1.5-flash")
            print("[AI] Using legacy google.generativeai SDK with gemini-1.5-flash")
        else:
            raise ImportError(
                "No Gemini SDK found. Install with: pip install google-genai"
            )

    def generate_reaction(self, subject: str, mood: str, callback: Callable[[str], None]):
        """
        Generates a reaction in a background thread to avoid UI freezing.
        :param subject: The content the pet is seeing (e.g. 'iPhone 16 Review')
        :param mood: The current pet state (e.g. 'WATCHING')
        :param callback: Function to call with the response string
        """
        if self.is_thinking:
            return

        def _think():
            self.is_thinking = True
            try:
                prompt = (
                    f"You are {self.personality}. Your human is currently in a {mood} mood "
                    f"and is looking at: '{subject}'. "
                    f"Give a very short, cute, and personality-driven 1-sentence reaction. "
                    f"Do not use emojis. Keep it under 15 words. Be a bit sassy but sweet."
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

                callback(text)
            except Exception as e:
                print(f"[AI Error] {e}")
                callback("Hmm... my brain is fuzzy!")
            finally:
                self.is_thinking = False

        thread = threading.Thread(target=_think, daemon=True)
        thread.start()
