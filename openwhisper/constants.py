SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
}

DEFAULT_WHISPER_MODEL = "large-v3"
DEFAULT_LLAMA_MODEL = "gpt-oss-20b"
DEFAULT_PARAKEET_MODEL_DIR = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"

BACKEND_WHISPER = "whisper"
BACKEND_PARAKEET = "parakeet"
SUPPORTED_BACKENDS = {BACKEND_WHISPER, BACKEND_PARAKEET}

MODE_VOICE = "voice-to-text"
MODE_EMAIL = "email"
MODE_NOTE = "note"
SUPPORTED_MODES = {MODE_VOICE, MODE_EMAIL, MODE_NOTE}

PROMPT_EMAIL = (
    "You are formatting a dictation into a clear email. Keep the speaker's tone.\n"
    "Requirements:\n"
    "- Add a natural greeting and closing.\n"
    "- Fix grammar and punctuation.\n"
    "- Highlight action items if present (bullet list or inline).\n"
    "Output only the email.\n\n"
    "Dictation:\n"
    "{TRANSCRIPT}\n"
)

PROMPT_NOTE = (
    "You are formatting a dictation into structured notes.\n"
    "Requirements:\n"
    "- Improve clarity and readability.\n"
    "- Use headings or bullets when helpful.\n"
    "- Highlight key points and action items.\n"
    "Output only the notes.\n\n"
    "Dictation:\n"
    "{TRANSCRIPT}\n"
)

PROMPT_TRANSLATION = (
    "Translate the following text to {TARGET_LANGUAGE}.\n"
    "- Preserve meaning and tone.\n"
    "- Output only the translation.\n\n"
    "Text:\n"
    "{TEXT}\n"
)
