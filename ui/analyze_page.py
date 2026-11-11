"""The "Analyze CVs" screen: shows the step bar and the current step."""
import streamlit as st

from ui import step_cvs, step_job, step_method, step_results
from ui.components import stepper

_STEPS = {1: step_method.render, 2: step_job.render, 3: step_cvs.render, 4: step_results.render}


def render_analyze_page() -> None:
    st.title("CV Analyzer")
    st.write("Compare CVs with a job description and shortlist the candidates who meet it.")
    stepper(st.session_state.step)
    _STEPS[st.session_state.step]()
