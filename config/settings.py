"""Central settings: file locations, limits and OpenRouter options.

Everything that might need changing lives here, so no other module contains
hard-coded paths or URLs. Values from the .env file are loaded once, below.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# --- Folders ---
CONFIG_FOLDER = ROOT / "config"
PROMPT_FOLDER = ROOT / "prompts"
CV_FOLDER = ROOT / "data" / "cvs"

# --- Document limits ---
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 150_000
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")

# --- OpenRouter ---
# "openrouter/free" lets OpenRouter pick a free model, so it works on a new key.
DEFAULT_MODEL = "openrouter/free"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def database_path() -> Path:
    """Where the SQLite database lives. Tests point this at a temporary file."""
    return Path(os.getenv("CV_ANALYZER_DB") or ROOT / "data" / "cv_analyzer.db")


def openrouter_base_url() -> str:
    return (os.getenv("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def openrouter_api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL


def load_json_config(file_name: str) -> dict:
    """Read one of the JSON files in the config folder."""
    return json.loads((CONFIG_FOLDER / file_name).read_text(encoding="utf-8"))


def load_prompt(file_name: str) -> str:
    """Read one of the AI instruction files in the prompts folder."""
    return (PROMPT_FOLDER / file_name).read_text(encoding="utf-8")
