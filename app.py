"""CV Analyzer: the entry point. Start it with start.bat, or:

    .venv\\Scripts\\python -m streamlit run app.py

This file only sets up the page and the navigation.
The screens live in ui/, the analysis in services/, and the database in database/.
"""
import streamlit as st

from database import db
from ui.analyze_page import render_analyze_page
from ui.database_page import render_database_page
from ui.state import init_state
from ui.theme import apply_theme

st.set_page_config(page_title="CV Analyzer", page_icon=":material/description:", layout="wide")

db.init_db()
init_state()
apply_theme()

navigation = st.navigation(
    [
        st.Page(render_analyze_page, title="Analyze CVs", icon=":material/fact_check:", default=True),
        st.Page(render_database_page, title="Shortlisted candidates", icon=":material/groups:", url_path="shortlisted"),
    ],
    position="top",
)
navigation.run()
