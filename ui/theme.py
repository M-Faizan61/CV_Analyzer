"""The look of the app: a small amount of CSS on top of Streamlit's own theme.

Colours and fonts come from .streamlit/config.toml. This file only adds what
Streamlit has no setting for: page width, the step bar and the result cards.
"""
import streamlit as st

_CSS = """
<style>
.block-container { max-width: 1000px; padding-top: 2.5rem; padding-bottom: 4rem; }

/* Step bar */
.stepper { display: flex; gap: .5rem; margin-bottom: 1.75rem; }
.step { flex: 1; padding: .55rem .75rem; border-radius: 8px; background: #F4F6F8;
        color: #52606D; font-size: .9rem; }
.step.current { background: #0F766E; color: #FFFFFF; font-weight: 600; }
.step.done { background: #E3F2F0; color: #0B5E58; }

/* Requirement checks */
.check { padding: .7rem .9rem; margin-bottom: .5rem; border-radius: 8px;
         border-left: 4px solid #CBD2D9; background: #F9FAFB; }
.check.met { border-left-color: #0F766E; }
.check.not-met { border-left-color: #B42318; }
.check.review { border-left-color: #B7791F; }
.check-title { font-weight: 600; color: #1F2933; }
.check-tag { font-weight: 400; font-size: .8rem; color: #52606D; margin-left: .4rem; }
.check-reason { font-size: .9rem; color: #3E4C59; margin-top: .15rem; }
.check-quote { font-size: .85rem; color: #52606D; margin-top: .3rem; padding-left: .6rem;
               border-left: 2px solid #E4E7EB; white-space: pre-wrap; }

/* Candidate details */
.record-name { font-size: 1.3rem; font-weight: 600; color: #1F2933; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .6rem 1.25rem; margin-bottom: 1rem; }
.fact-label { font-size: .8rem; color: #52606D; }
.fact-value { color: #1F2933; overflow-wrap: anywhere; }

@media (max-width: 640px) {
    .stepper { flex-direction: column; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
