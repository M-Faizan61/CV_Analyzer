"""The "Shortlisted candidates" screen: create, read, update and delete saved records.

  Create  the "Add a record" tab
  Read    the table, filters and search, then Details on an open record
  Update  Edit on an open record
  Delete  Delete on an open record, or remove a whole job
"""
import streamlit as st

from database import db
from services.export import csv_bytes
from ui.components import findings_from_record, render_facts, render_findings, safe_heading, saved_facts, years_text

_ALL = "All"
_NEW_JOB = "New job"
_EMPTY_RECORD = {"name": "", "email": "", "phone": "", "location": "", "current_title": "", "candidate_type": "Not clear",
                 "total_years": None, "education": "", "skills": "", "status": "New", "notes": ""}


# --- Shared pieces ---
def _detail_fields(prefix: str, record: dict) -> dict:
    """The boxes shared by the Add and Edit forms. Returns what is in them."""
    years = record["total_years"]
    left, right = st.columns(2)
    name = left.text_input("Full name", value=record["name"], key=f"{prefix}_name")
    email = right.text_input("Email", value=record["email"], key=f"{prefix}_email")
    phone = left.text_input("Phone", value=record["phone"], key=f"{prefix}_phone")
    location = right.text_input("Location", value=record["location"], key=f"{prefix}_location")
    current_title = left.text_input("Current role", value=record["current_title"], key=f"{prefix}_title")
    education = right.text_input("Education", value=record["education"], key=f"{prefix}_education")
    total_years = left.number_input("Total experience (years)", value=None if years is None else min(years, 60.0),
                                    min_value=0.0, max_value=60.0, step=0.5, key=f"{prefix}_years")
    candidate_type = right.selectbox("Candidate type", db.CANDIDATE_TYPES, index=db.CANDIDATE_TYPES.index(record["candidate_type"]),
                                     key=f"{prefix}_type")
    skills = st.text_input("Skills", value=record["skills"], key=f"{prefix}_skills", placeholder="Python, SQL, Git")
    status = left.selectbox("Status", db.STATUSES, index=db.STATUSES.index(record["status"]), key=f"{prefix}_status")
    notes = right.text_input("Notes", value=record["notes"], key=f"{prefix}_notes")
    return {"name": name, "email": email, "phone": phone, "location": location, "current_title": current_title,
            "education": education, "total_years": total_years, "candidate_type": candidate_type, "skills": skills,
            "status": status, "notes": notes}


def _show_message(text: str) -> None:
    """Keep a message for the next run, so it is shown after the page refreshes."""
    st.session_state.database_message = text


# --- Create ---
def _chosen_job_id(job_ids: dict, choice: str, new_title: str) -> int:
    if choice != _NEW_JOB:
        return job_ids[choice]
    if not new_title.strip():
        raise ValueError("Please enter the job title.")
    return db.save_job(new_title, "", [], "Manual")


def _add_tab() -> None:
    st.write("Add a candidate by hand, for example someone who was referred to you.")

    job_ids = {f"{job['title']} (#{job['id']})": job["id"] for job in db.list_jobs()}
    choice = st.selectbox("Job", [_NEW_JOB, *job_ids], key="add_job")
    new_title = st.text_input("New job title", key="add_job_title") if choice == _NEW_JOB else ""

    # The form key changes after a save, which empties the boxes. A failed save keeps what was typed.
    version = st.session_state.add_form_version
    with st.form(f"add_record_{version}", border=False):
        details = _detail_fields(f"add_{version}", _EMPTY_RECORD)
        submitted = st.form_submit_button("Add record", type="primary")

    if submitted:
        try:
            db.check_details(details)
            db.create_candidate(_chosen_job_id(job_ids, choice, new_title), **details)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.add_form_version += 1
            _show_message(f"{details['name'].strip()} was added.")
            st.rerun()


# --- Read ---
def _filters() -> dict:
    """Show the filter boxes and return the chosen values."""
    job_ids = {f"{job['title']} (#{job['id']})": job["id"] for job in db.list_jobs()}
    search_box, job_box, status_box, type_box = st.columns([3, 3, 2, 2])
    search = search_box.text_input("Search", placeholder="Name, skill, city...", key="filter_search")
    job = job_box.selectbox("Job", [_ALL, *job_ids], key="filter_job")
    status = status_box.selectbox("Status", [_ALL, *db.STATUSES], key="filter_status")
    candidate_type = type_box.selectbox("Type", [_ALL, *db.CANDIDATE_TYPES], key="filter_type")
    return {
        "search": search,
        "job_id": job_ids.get(job),
        "status": "" if status == _ALL else status,
        "candidate_type": "" if candidate_type == _ALL else candidate_type,
    }


def _table_rows(records: list[dict]) -> list[dict]:
    return [{
        "Name": record["name"],
        "Job": record["job_title"],
        "Rank": record["rank"],
        "Match": record["match_score"],
        "Status": record["status"],
        "Type": record["candidate_type"],
        "Experience": years_text(record["total_years"]),
        "Email": record["email"],
        "Phone": record["phone"],
        "Location": record["location"],
        "Education": record["education"],
        "Added by": record["decided_by"],
        "Saved on": record["created_at"][:10],
    } for record in records]


def _record_view(record: dict) -> None:
    render_facts(saved_facts(record), empty="Not added")
    findings = findings_from_record(record)
    if findings:
        with st.expander("Requirement checks"):
            render_findings(findings)
    if record["cv_text"]:
        with st.expander("CV text"):
            st.text(record["cv_text"])


# --- Update ---
def _record_edit(record: dict) -> None:
    with st.form(f"edit_record_{record['id']}", border=False):
        details = _detail_fields(f"edit_{record['id']}", record)
        st.caption("Match and rank are calculated by the system, so they cannot be typed in. "
                   "What you change here is kept if this CV is analyzed again.")
        submitted = st.form_submit_button("Save changes", type="primary")

    if submitted:
        try:
            db.update_candidate(record["id"], **details)
        except ValueError as error:
            st.error(str(error))
        else:
            _show_message("Changes saved.")
            st.rerun()


# --- Delete ---
def _delete_record(candidate_id: int) -> None:
    db.delete_candidate(candidate_id)
    st.session_state.pop("open_record", None)
    _show_message("Record deleted.")


def _delete_job(job_id: int) -> None:
    db.delete_job(job_id)
    st.session_state.pop("filter_job", None)
    st.session_state.pop("open_record", None)
    _show_message("Job and its records deleted.")


def _record_delete(record: dict) -> None:
    st.write("This permanently removes the record. It cannot be undone.")
    sure = st.checkbox("Yes, delete this record", key=f"confirm_delete_{record['id']}")
    st.button("Delete record", key=f"delete_{record['id']}", disabled=not sure, on_click=_delete_record, args=(record["id"],))


def _job_delete_control(job_id: int, record_count: int) -> None:
    with st.popover("Delete this job"):
        st.write(f"This permanently removes the job and its {record_count} record(s). It cannot be undone.")
        st.button("Yes, delete the job", key=f"delete_job_{job_id}", on_click=_delete_job, args=(job_id,))


# --- The page ---
def _open_record(records: list[dict]) -> None:
    """Open one record, with a tab each for reading, changing and deleting it."""
    st.subheader("Open a record")
    labels = {f"{record['name']}, {record['job_title']} (#{record['id']})": record["id"] for record in records}
    if st.session_state.get("open_record") not in labels:
        st.session_state.pop("open_record", None)
    choice = st.selectbox("Candidate", list(labels), key="open_record")
    record = db.get_candidate(labels[choice])

    with st.container(border=True):
        safe_heading(record["name"])
        st.text(f"{record['job_title']}. {record['reason']}".strip(" ."))
        # The key keeps the chosen tab open when a message above it appears or disappears.
        details, edit, delete = st.tabs(["Details", "Edit", "Delete"], key=f"record_tabs_{record['id']}")
        with details:
            _record_view(record)
        with edit:
            _record_edit(record)
        with delete:
            _record_delete(record)


def _records_tab() -> None:
    all_records = db.list_candidates()
    if not db.list_jobs():
        st.info("No records yet. Run an analysis, or use the Add a record tab.")
        return

    total, students, employees, jobs = st.columns(4)
    total.metric("Candidates", len(all_records))
    students.metric("Students", sum(record["candidate_type"] == "Student" for record in all_records))
    employees.metric("Employees", sum(record["candidate_type"] == "Employee" for record in all_records))
    jobs.metric("Jobs", len(db.list_jobs()))

    filters = _filters()
    records = db.list_candidates(**filters)

    if not records:
        st.write("No records match these filters.")
    else:
        rows = _table_rows(records)
        st.dataframe(rows, hide_index=True, placeholder="-", column_config={
            "Rank": st.column_config.NumberColumn(width="small"),
            "Match": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        })

    with st.container(horizontal=True):
        if records:
            st.download_button("Download these records (CSV)", csv_bytes(_table_rows(records)), file_name="shortlisted_candidates.csv",
                               mime="text/csv", key="download_records")
        if filters["job_id"] is not None:
            _job_delete_control(filters["job_id"], len(records))

    if records:
        _open_record(records)


def render_database_page() -> None:
    st.title("Shortlisted candidates")
    st.write("Add, view, change and delete candidate records. They are stored only on this computer.")

    if "database_message" in st.session_state:
        st.success(st.session_state.pop("database_message"))

    records, add = st.tabs(["Records", "Add a record"], key="records_page_tabs")
    with records:
        _records_tab()
    with add:
        _add_tab()
