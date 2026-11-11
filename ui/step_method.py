"""Step 1: choose the analysis method, Manual or AI."""
import streamlit as st

from config import settings
from services.openrouter_client import OpenRouterError, test_connection
from ui.state import bound_key, go_to_step, resolved_api_key


def _choose_manual() -> None:
    st.session_state.method = "manual"
    go_to_step(2)


def _choose_ai() -> None:
    st.session_state.method = "ai"


def _method_cards() -> None:
    ai_selected = st.session_state.method == "ai"
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("#### Manual")
        st.write("No API key needed. Uses built-in rules, and nothing leaves this computer.")
        st.caption("Best when CVs clearly list skills and years.")
        st.button("Use Manual", key="use_manual", type="secondary" if ai_selected else "primary", width="stretch", on_click=_choose_manual)
    with right, st.container(border=True):
        st.markdown("#### AI with OpenRouter")
        st.write("Uses your API key to read any CV layout and check harder requirements.")
        st.caption("CV text is sent to the AI model you choose.")
        st.button("Use AI", key="use_ai", type="primary" if ai_selected else "secondary", width="stretch", on_click=_choose_ai)


def _ai_settings() -> None:
    st.divider()
    st.subheader("OpenRouter settings")

    has_env_key = bool(settings.openrouter_api_key())
    st.session_state.api_key = st.text_input(
        "API key", key=bound_key("api_key"), type="password",
        placeholder="Using the key from your .env file" if has_env_key else "sk-or-v1-...",
        help="Create a key at openrouter.ai/keys. A key typed here is kept only until you close this tab.")
    st.session_state.model = st.text_input(
        "Model", key=bound_key("model"),
        help="Any model ID from openrouter.ai/models. openrouter/free picks a free model for you.")
    st.caption("Free models may keep or learn from what you send. For real CVs, choose a paid model with a privacy policy you accept.")

    if st.button("Test connection", key="test_connection", disabled=not resolved_api_key()):
        try:
            with st.spinner("Contacting OpenRouter..."):
                test_connection(resolved_api_key(), st.session_state.model)
            st.success("Connected. This key and model work.")
        except OpenRouterError as error:
            st.error(str(error))

    st.session_state.ai_consent = st.checkbox("I agree to send job and CV text to OpenRouter.", key=bound_key("ai_consent"))

    ready = bool(resolved_api_key()) and st.session_state.ai_consent and bool(st.session_state.model.strip())
    st.button("Next: job description", key="ai_next", type="primary", disabled=not ready, on_click=go_to_step, args=(2,))


def render() -> None:
    st.subheader("Step 1: How do you want to analyze the CVs?")
    _method_cards()
    if st.session_state.method == "ai":
        _ai_settings()
