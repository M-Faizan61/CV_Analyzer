"""Step 2: enter the job description, then review the requirements found in it."""
import hashlib

import streamlit as st

from models.schemas import Requirement
from services import pipeline
from services.document_reader import read_document
from services.job_parser import guess_job_title, validate_requirements
from services.openrouter_client import OpenRouterError
from ui.state import ai_options, bound_key, go_to_step

_PRIORITIES = {"mandatory": "Must have", "preferred": "Nice to have", "ignore": "Ignore"}
_TYPES = {"skill": "Skill", "experience": "Experience", "education": "Education", "other": "Other"}
_MATCH_RULES = {"ALL": "All", "ANY": "Any"}
_COLUMNS = ["text", "priority", "type", "skills", "match", "min_years"]
_ROW_HEIGHT = 35


def _reverse(mapping: dict) -> dict:
    return {label: value for value, label in mapping.items()}


def _source_id() -> str:
    """Identifies the text and method that the requirements were read from."""
    source = f"{st.session_state.method}\n{st.session_state.job_text}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _load_job_file(uploader_key: str) -> None:
    """Copy an uploaded job description into the text box."""
    upload = st.session_state.get(uploader_key)
    if upload is None:
        return
    try:
        st.session_state.input_job_text = read_document(upload.name, upload.getvalue())
    except ValueError as error:
        st.session_state.job_file_error = str(error)


def _to_row(requirement: Requirement) -> dict:
    """Convert a requirement into a row of the review table."""
    row = requirement.model_dump()
    row.update(priority=_PRIORITIES[requirement.importance], type=_TYPES[requirement.kind],
               match=_MATCH_RULES[requirement.operator])
    return row


def _from_row(row: dict, number: int) -> dict:
    """Convert a row of the review table back into requirement data."""
    min_years = row.get("min_years")
    return {
        "id": f"R{number}",  # numbered again, because rows can be added or deleted
        "text": (row.get("text") or "").strip(),
        "importance": _reverse(_PRIORITIES).get(row.get("priority"), "mandatory"),
        "kind": _reverse(_TYPES).get(row.get("type"), "skill"),
        "skills": (row.get("skills") or "").strip(),
        "operator": _reverse(_MATCH_RULES).get(row.get("match"), "ALL"),
        "min_years": None if min_years is None or min_years != min_years else float(min_years),  # NaN != NaN
        "degree": row.get("degree") or "",
        "degree_field": row.get("degree_field") or "",
    }


def _read_requirements() -> None:
    """Read the job description and fill the review table."""
    try:
        with st.spinner("Reading the job description..."):
            requirements = pipeline.read_requirements(st.session_state.job_text, ai_options())
    except (ValueError, OpenRouterError) as error:
        st.error(str(error))
        return

    used_first = sorted(requirements, key=lambda item: item.importance == "ignore")  # a stable sort keeps the job's order
    st.session_state.requirement_rows = [_to_row(item) for item in used_first if item.kind != "personal"]
    st.session_state.personal_rows = [item.model_dump() for item in requirements if item.kind == "personal"]
    st.session_state.requirements_source = _source_id()
    st.session_state.editor_version += 1
    if not st.session_state.job_title.strip():
        st.session_state.suggested_title = guess_job_title(st.session_state.job_text)
    st.rerun()


def _review_table() -> list[dict]:
    """Let the user correct the requirements. Returns the edited rows."""
    st.subheader("Check the requirements")
    st.write("This is what candidates will be judged on. Change anything that is wrong, then continue.")

    rows = st.session_state.requirement_rows
    edited = st.data_editor(
        rows,
        key=f"requirements_editor_{st.session_state.editor_version}",
        column_order=_COLUMNS,
        num_rows="dynamic",
        hide_index=True,
        height=_ROW_HEIGHT * (len(rows) + 2) + 3,  # every row visible, plus the header and the "add row" line
        column_config={
            "text": st.column_config.TextColumn("Requirement", width=300, required=True),
            "priority": st.column_config.SelectboxColumn("Priority", width=105, options=list(_PRIORITIES.values()), required=True, default="Must have"),
            "type": st.column_config.SelectboxColumn("Type", width=90, options=list(_TYPES.values()), required=True, default="Skill"),
            "skills": st.column_config.TextColumn("Skills", width=135, help="Separate skill names with commas."),
            "match": st.column_config.SelectboxColumn("Match", width=65, options=list(_MATCH_RULES.values()), required=True, default="All",
                                                      help="All: every skill is needed. Any: one skill is enough."),
            "min_years": st.column_config.NumberColumn("Min years", width=80, min_value=0, max_value=60),
        },
    )

    st.caption("**Must have**: a candidate without it is not shortlisted. **Nice to have**: only improves the ranking. "
               "**Ignore**: not used. Lines that are not requirements start as Ignore, at the bottom of the table.")

    if st.session_state.personal_rows:
        conditions = "; ".join(row["text"] for row in st.session_state.personal_rows)
        st.warning(f"Not used in the analysis: {conditions}. Personal conditions must be checked by a person under your hiring policy.")

    unchecked = [row["text"] for row in edited if row.get("type") == "Other" and row.get("priority") == "Nice to have"]
    if unchecked and st.session_state.method == "manual":
        st.info(f"{len(unchecked)} line(s) cannot be proven by rules alone, so they start as Nice to have. "
                "Change them to Must have if they are essential.")
    return edited


def _save_and_continue(edited: list[dict]) -> None:
    """Validate the reviewed requirements and move on."""
    filled_in = [row for row in edited if (row.get("text") or "").strip()]
    rows = [_from_row(row, number) for number, row in enumerate(filled_in, 1)]
    personal = [{**row, "id": f"P{number}"} for number, row in enumerate(st.session_state.personal_rows, 1)]
    try:
        requirements = validate_requirements(rows + personal)
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state.requirements = requirements
    st.session_state.requirement_rows = [_to_row(item) for item in requirements if item.kind != "personal"]
    st.session_state.editor_version += 1
    go_to_step(3)
    st.rerun()


def render() -> None:
    st.subheader("Step 2: Add the job description")

    # A widget's value can only be set before the widget is drawn, so this comes first.
    if "suggested_title" in st.session_state:
        st.session_state.input_job_title = st.session_state.pop("suggested_title")

    st.session_state.job_title = st.text_input("Job title", key=bound_key("job_title"), placeholder="WordPress Developer")
    uploader_key = f"job_file_{st.session_state.uploader_version}"
    st.file_uploader("Upload a job description (optional)", type=["pdf", "docx", "txt"], key=uploader_key,
                     on_change=_load_job_file, args=(uploader_key,))
    if st.session_state.get("job_file_error"):
        st.error(st.session_state.pop("job_file_error"))
    st.session_state.job_text = st.text_area("Job description", key=bound_key("job_text"), height=220,
                                             placeholder="Paste the job description here")

    if st.button("Read requirements", key="read_requirements", type="primary", disabled=not st.session_state.job_text.strip()):
        _read_requirements()

    edited = None
    if st.session_state.requirement_rows:
        if st.session_state.requirements_source == _source_id():
            edited = _review_table()
        else:
            st.warning("The job description has changed. Click Read requirements again.")

    st.write("")
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("Back", key="job_back", on_click=go_to_step, args=(1,))
        next_clicked = st.button("Next: add CVs", key="job_next", type="primary", disabled=edited is None)
    if next_clicked:
        _save_and_continue(edited)
