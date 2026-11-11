"""Step 3: add CVs in any of three ways, then run the analysis."""
import streamlit as st

from config.settings import CV_FOLDER, SUPPORTED_EXTENSIONS
from services import pipeline
from services.manual_cv import build_cv_text
from services.openrouter_client import OpenRouterError
from services.pipeline import CvInput
from ui.state import ai_options, go_to_step

_MAX_LISTED_HEIGHT = 320


def _add_cvs(incoming: list[CvInput]) -> None:
    """Add CVs to the list, skipping exact copies of a CV already there."""
    added, skipped = pipeline.new_cvs_only(st.session_state.cvs, incoming)
    st.session_state.cvs = st.session_state.cvs + added
    message = f"Added {len(added)} CV(s)."
    if skipped:
        message += f" Skipped {skipped} duplicate(s)."
    st.session_state.cv_message = message


def _upload_tab() -> None:
    uploads = st.file_uploader("Choose CV files (PDF, DOCX or TXT, up to 10 MB each)", type=["pdf", "docx", "txt"],
                               accept_multiple_files=True, key=f"cv_upload_{st.session_state.uploader_version}")
    if uploads:
        _add_cvs([CvInput(name=upload.name, source="Upload", content=upload.getvalue()) for upload in uploads])
        st.session_state.uploader_version += 1  # empties the box, so the files are not added again
        st.rerun()


def _manual_tab() -> None:
    with st.form("manual_cv", clear_on_submit=True, border=False):
        left, right = st.columns(2)
        name = left.text_input("Full name", key="manual_name")
        email = right.text_input("Email")
        phone = left.text_input("Phone")
        location = right.text_input("Location", placeholder="Lahore, Pakistan")
        total_years = left.number_input("Total experience (years)", min_value=0.0, max_value=60.0, step=0.5)
        education = right.text_input("Education", placeholder="BS Computer Science")
        skills = st.text_area("Skills, one per line", key="manual_skills", height=110, placeholder="Python: 3 years\nSQL: 2 years\nGit")
        work = st.text_area("Work experience", height=110, placeholder="Python Developer - ABC Ltd (2022 - Present)\n- Built reporting tools")
        other = st.text_area("Anything else, or paste the whole CV here", height=110)
        submitted = st.form_submit_button("Add this CV", type="primary")

    if submitted:
        text = build_cv_text(name, email, phone, location, total_years, skills, work, education, other)
        if not name.strip() and not other.strip():
            st.error("Enter a name, or paste the CV text.")
        elif len(text.strip()) < 20:
            st.error("Please add more details, such as skills or experience.")
        else:
            _add_cvs([CvInput(name=f"{name.strip() or 'Pasted CV'} (typed)", source="Manual entry", text=text, known_name=name.strip())])
            st.rerun()


def _folder_tab() -> None:
    st.write("Add every CV saved in this folder:")
    st.code(str(CV_FOLDER), language=None)
    paths = sorted(path for path in CV_FOLDER.glob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS)
    if not paths:
        st.info("This folder has no PDF, DOCX or TXT files yet.")
        return
    if st.button(f"Add all {len(paths)} files", key="add_folder", type="primary"):
        cvs = []
        for path in paths:
            try:
                cvs.append(CvInput(name=path.name, source="Folder", content=path.read_bytes()))
            except OSError:
                st.warning(f"Could not open {path.name}. It may be open in another program.")
        _add_cvs(cvs)
        st.rerun()


def _remove_cv(index: int) -> None:
    st.session_state.cvs = [cv for number, cv in enumerate(st.session_state.cvs) if number != index]


def _added_list() -> None:
    cvs = st.session_state.cvs
    st.subheader(f"CVs added: {len(cvs)}")
    if not cvs:
        st.caption("Nothing added yet.")
        return
    with st.container(height=min(_MAX_LISTED_HEIGHT, 58 * len(cvs) + 16), border=True):
        for index, cv in enumerate(cvs):
            name, source, remove = st.columns([6, 2, 1], vertical_alignment="center")
            name.text(cv.name)
            source.caption(cv.source)
            remove.button("Remove", key=f"remove_{index}_{cv.fingerprint[:8]}", type="tertiary", on_click=_remove_cv, args=(index,))


def _run_analysis() -> None:
    """Analyze every CV, save the shortlist, and open the results."""
    progress = st.progress(0.0, text="Starting...")

    def show_progress(number: int, total: int, name: str) -> None:
        progress.progress((number - 1) / total, text=f"Analyzing CV {number} of {total}: {name}")

    ai = ai_options()
    requirements = st.session_state.requirements
    try:
        results = pipeline.analyze_batch(st.session_state.cvs, requirements, ai, show_progress)
        job_id, saved = pipeline.save_shortlist(st.session_state.job_title, st.session_state.job_text, requirements, results, ai)
    except OpenRouterError as error:
        progress.empty()
        st.error(f"The analysis stopped. {error}")
        return

    st.session_state.batch = {"results": results, "job_id": job_id, "saved": saved, "added_by_reviewer": set()}
    go_to_step(4)
    st.rerun()


def render() -> None:
    st.subheader("Step 3: Add the CVs")

    upload, manual, folder = st.tabs(["Upload files", "Enter manually", "Use CV folder"])
    with upload:
        _upload_tab()
    with manual:
        _manual_tab()
    with folder:
        _folder_tab()

    if "cv_message" in st.session_state:
        st.success(st.session_state.pop("cv_message"))

    _added_list()

    st.write("")
    count = len(st.session_state.cvs)
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("Back", key="cvs_back", on_click=go_to_step, args=(2,))
        analyze_clicked = st.button(f"Analyze {count} CV{'' if count == 1 else 's'}", key="analyze", type="primary", disabled=not count)
    if analyze_clicked:
        _run_analysis()
