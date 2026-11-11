"""Everything the app remembers between clicks.

Streamlit reruns the page on every click and forgets widgets that are not on
screen, so moving between steps would lose what was typed. To prevent that, the
values live in the session state under the names in _new_session(), and bound_key()
connects each input box to its value.

Nothing here is written to disk. The API key stays in memory until the tab closes.
"""
import streamlit as st

from config import settings
from services.pipeline import AiOptions


def _new_session() -> dict:
    return {
        "step": 1,
        "method": "",  # "manual" or "ai"
        "api_key": "",
        "model": settings.openrouter_model(),
        "ai_consent": False,
        "job_title": "",
        "job_text": "",
        "requirements": [],  # the reviewed list used for the analysis
        "requirement_rows": [],  # rows of the review table
        "personal_rows": [],  # personal conditions, shown apart and never scored
        "requirements_source": "",  # the job text the rows were read from
        "editor_version": 0,
        "cvs": [],
        "uploader_version": 0,
        "add_form_version": 0,
        "batch": None,  # the finished analysis
    }


def init_state() -> None:
    for name, value in _new_session().items():
        st.session_state.setdefault(name, value)


def bound_key(name: str) -> str:
    """Return a widget key whose value survives leaving the step and coming back."""
    widget_key = f"input_{name}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state[name]
    return widget_key


def go_to_step(step: int) -> None:
    st.session_state.step = step


def start_over() -> None:
    """Begin a new analysis. The chosen method and API key are kept."""
    keep = {name: st.session_state[name] for name in ("method", "api_key", "model", "ai_consent")}
    keep["uploader_version"] = st.session_state.uploader_version + 1  # empties the upload boxes
    for name, value in _new_session().items():
        st.session_state[name] = keep.get(name, value)
    st.session_state.step = 2
    for widget_key in ("input_job_title", "input_job_text"):
        st.session_state.pop(widget_key, None)


def resolved_api_key() -> str:
    """The key typed on screen, otherwise the one in the .env file."""
    return st.session_state.api_key.strip() or settings.openrouter_api_key()


def ai_options() -> AiOptions | None:
    """Options for the pipeline, or None when the Manual method is selected."""
    if st.session_state.method != "ai":
        return None
    return AiOptions(api_key=resolved_api_key(), model=st.session_state.model.strip())
