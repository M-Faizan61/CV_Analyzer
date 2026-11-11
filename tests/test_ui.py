"""Click through the real screens with Streamlit's test runner. No external calls are made."""
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from database import db
from services.manual_cv import build_cv_text

ROOT = Path(__file__).resolve().parents[1]
JOB = "Python Developer\nRequirements:\nPython\nNice to have:\nDocker"


def open_app():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    return app


def click(app, key):
    app.button(key=key).click().run()
    assert not app.exception
    return app


def go_to_cv_step(app):
    click(app, "use_manual")
    app.text_area(key="input_job_text").set_value(JOB).run()
    click(app, "read_requirements")
    return click(app, "job_next")


def add_manual_cv(app, name="Ali Raza", skills="Python: 3 years\nDocker: 1 year"):
    app.text_input(key="manual_name").set_value(name)
    app.text_area(key="manual_skills").set_value(skills)
    form_button = next(button for button in app.button if button.label == "Add this CV")
    form_button.click().run()
    assert not app.exception
    return app


def database_screen():
    """AppTest runs this on its own, so it imports what the real app would."""
    from ui.database_page import render_database_page
    from ui.state import init_state

    init_state()
    render_database_page()


def test_first_screen_offers_both_methods():
    app = open_app()
    assert {button.label for button in app.button} >= {"Use Manual", "Use AI"}


def test_manual_method_full_journey_saves_to_the_database():
    app = go_to_cv_step(open_app())
    assert app.session_state["step"] == 3
    assert app.button(key="analyze").disabled

    add_manual_cv(app)
    assert len(app.session_state["cvs"]) == 1
    assert app.button(key="analyze").label == "Analyze 1 CV"

    click(app, "analyze")
    assert app.session_state["step"] == 4
    assert [metric.value for metric in app.metric] == ["1", "1", "0", "0"]

    records = db.list_candidates()
    assert [record["name"] for record in records] == ["Ali Raza"]
    assert records[0]["job_title"] == "Python Developer"  # suggested from the job text


def test_requirements_are_stale_after_the_job_text_changes():
    app = open_app()
    click(app, "use_manual")
    app.text_area(key="input_job_text").set_value(JOB).run()
    click(app, "read_requirements")
    assert not app.button(key="job_next").disabled

    app.text_area(key="input_job_text").set_value("MySQL required").run()
    assert app.button(key="job_next").disabled
    assert any("changed" in warning.value for warning in app.warning)


def test_typed_text_survives_going_back_and_forward():
    app = go_to_cv_step(open_app())
    click(app, "cvs_back")
    assert app.text_area(key="input_job_text").value == JOB
    assert app.text_input(key="input_job_title").value == "Python Developer"


def test_ai_method_needs_a_key_and_consent():
    app = open_app()
    click(app, "use_ai")
    assert app.button(key="ai_next").disabled

    app.text_input(key="input_api_key").set_value("test-key").run()
    assert app.button(key="ai_next").disabled

    app.checkbox(key="input_ai_consent").check().run()
    assert not app.button(key="ai_next").disabled
    click(app, "ai_next")
    assert app.session_state["step"] == 2


def test_key_from_env_file_is_accepted(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    app = open_app()
    click(app, "use_ai")
    app.checkbox(key="input_ai_consent").check().run()
    assert not app.button(key="ai_next").disabled


def test_a_rejected_key_is_reported_without_crashing():
    from services.openrouter_client import OpenRouterError

    app = open_app()
    click(app, "use_ai")
    app.text_input(key="input_api_key").set_value("wrong-key").run()
    with patch("ui.step_method.test_connection", side_effect=OpenRouterError("OpenRouter rejected this API key.")):
        click(app, "test_connection")
    assert any("rejected" in error.value for error in app.error)


def test_needs_review_candidate_can_be_added_by_a_person():
    app = go_to_cv_step(open_app())
    add_manual_cv(app, skills="Planning to learn Python soon")
    click(app, "analyze")
    assert [metric.value for metric in app.metric] == ["1", "0", "1", "0"]
    assert db.list_candidates() == []

    button = next(button for button in app.button if button.label == "Add to shortlist")
    button.click().run()
    assert not app.exception
    assert [record["decided_by"] for record in db.list_candidates()] == ["Reviewer"]


def test_start_over_clears_the_job_and_keeps_the_method():
    app = go_to_cv_step(open_app())
    add_manual_cv(app)
    click(app, "analyze")
    click(app, "start_over")
    assert app.session_state["step"] == 2
    assert app.session_state["method"] == "manual"
    assert app.text_area(key="input_job_text").value == ""
    assert app.session_state["cvs"] == []


def save_sample_record() -> int:
    from helpers import skill, typed_cv
    from services import pipeline

    cv = build_cv_text(name="Ali Raza", email="ali@example.com", skills="Python: 3 years\nGit")
    requirements = [skill("python")]
    pipeline.save_shortlist("Developer", "Job", requirements, pipeline.analyze_batch([typed_cv(cv)], requirements))
    return db.list_candidates()[0]["id"]


def open_records_page():
    page = AppTest.from_function(database_screen, default_timeout=30).run()
    assert not page.exception
    return page


def press(page, label):
    next(button for button in page.button if button.label == label).click().run()
    assert not page.exception
    return page


# --- Read ---
def test_records_page_shows_saved_records():
    save_sample_record()
    page = open_records_page()
    assert page.metric[0].value == "1"
    assert page.selectbox(key="open_record").value.startswith("Ali Raza")


def test_records_page_search_finds_a_record():
    save_sample_record()
    page = open_records_page()
    page.text_input(key="filter_search").set_value("Nobody").run()
    assert any("No records match" in text.value for text in page.markdown)


def test_empty_records_page_explains_itself():
    page = open_records_page()
    assert any("No records yet" in info.value for info in page.info)


# --- Create ---
def fill_new_record(page, name, email=""):
    version = page.session_state["add_form_version"]
    page.text_input(key=f"add_{version}_name").set_value(name)
    page.text_input(key=f"add_{version}_email").set_value(email)
    return version


def test_a_record_can_be_added_by_hand_for_a_new_job():
    page = open_records_page()
    page.text_input(key="add_job_title").set_value("Accountant").run()
    version = fill_new_record(page, "Sara Khan", "sara@example.com")
    page.selectbox(key=f"add_{version}_type").set_value("Student")
    press(page, "Add record")

    record = db.list_candidates()[0]
    assert (record["name"], record["job_title"], record["candidate_type"]) == ("Sara Khan", "Accountant", "Student")
    assert record["decided_by"] == "Manual entry"
    assert any("Sara Khan was added" in message.value for message in page.success)


def test_a_record_can_be_added_to_an_existing_job():
    save_sample_record()
    page = open_records_page()
    page.selectbox(key="add_job").set_value(page.selectbox(key="add_job").options[1]).run()
    fill_new_record(page, "Sara Khan")
    press(page, "Add record")
    assert {record["job_title"] for record in db.list_candidates()} == {"Developer"}
    assert len(db.list_candidates()) == 2


def test_a_mistake_in_the_add_form_keeps_the_typed_text():
    page = open_records_page()
    page.text_input(key="add_job_title").set_value("Accountant").run()
    version = fill_new_record(page, "Sara Khan", "not-an-email")
    press(page, "Add record")
    assert any("email" in error.value for error in page.error)
    assert page.text_input(key=f"add_{version}_name").value == "Sara Khan"
    assert db.list_candidates() == []
    assert db.list_jobs() == []  # a failed save leaves nothing behind


def test_adding_needs_a_job_title_for_a_new_job():
    page = open_records_page()
    fill_new_record(page, "Sara Khan")
    press(page, "Add record")
    assert any("job title" in error.value for error in page.error)
    assert db.list_jobs() == []


# --- Update ---
def test_any_detail_of_a_record_can_be_edited_on_screen():
    record_id = save_sample_record()
    page = open_records_page()
    page.text_input(key=f"edit_{record_id}_name").set_value("Ali R. Khan")
    page.text_input(key=f"edit_{record_id}_phone").set_value("03009998888")
    page.selectbox(key=f"edit_{record_id}_type").set_value("Student")
    page.selectbox(key=f"edit_{record_id}_status").set_value("Interview")
    page.text_input(key=f"edit_{record_id}_notes").set_value("Call on Monday")
    press(page, "Save changes")

    saved = db.get_candidate(record_id)
    assert saved["name"] == "Ali R. Khan"
    assert saved["phone"] == "03009998888"
    assert saved["candidate_type"] == "Student"
    assert (saved["status"], saved["notes"]) == ("Interview", "Call on Monday")
    assert any("Changes saved" in message.value for message in page.success)


def test_a_bad_edit_is_refused_and_changes_nothing():
    record_id = save_sample_record()
    page = open_records_page()
    page.text_input(key=f"edit_{record_id}_email").set_value("not-an-email")
    press(page, "Save changes")
    assert any("email" in error.value for error in page.error)
    assert db.get_candidate(record_id)["email"] == "ali@example.com"


# --- Delete ---
def test_delete_needs_confirmation_then_removes_the_record():
    record_id = save_sample_record()
    page = open_records_page()
    assert page.button(key=f"delete_{record_id}").disabled

    page.checkbox(key=f"confirm_delete_{record_id}").check().run()
    page.button(key=f"delete_{record_id}").click().run()
    assert not page.exception
    assert db.list_candidates() == []
    assert any("Record deleted" in message.value for message in page.success)


def test_a_whole_job_can_be_deleted():
    save_sample_record()
    job_id = db.list_jobs()[0]["id"]
    page = open_records_page()
    page.selectbox(key="filter_job").set_value(page.selectbox(key="filter_job").options[1]).run()
    page.button(key=f"delete_job_{job_id}").click().run()
    assert not page.exception
    assert db.list_jobs() == []
    assert db.list_candidates() == []


@pytest.mark.parametrize("name,other,message", [("", "", "Enter a name"), ("Al", "", "more details")])
def test_manual_form_explains_missing_details(name, other, message):
    app = go_to_cv_step(open_app())
    app.text_input(key="manual_name").set_value(name)
    next(button for button in app.button if button.label == "Add this CV").click().run()
    assert any(message in error.value for error in app.error)
    assert app.session_state["cvs"] == []
