import sqlite3

import pytest

from config.settings import database_path
from database import db
from helpers import skill, typed_cv
from services import pipeline

CV = "Ali Raza\nali@example.com | +92 300 1007919 | Lahore, Pakistan\nSKILLS\nPython: 3 years"


def save_one(cv_text=CV, requirement=None, title="Developer"):
    requirement = requirement or skill("python")
    results = pipeline.analyze_batch([typed_cv(cv_text)], [requirement])
    return pipeline.save_shortlist(title, "Job text", [requirement], results)


def test_shortlisted_candidate_is_saved_with_their_details():
    job_id, saved = save_one()
    assert saved == 1
    record = db.list_candidates()[0]
    assert record["job_id"] == job_id
    assert record["name"] == "Ali Raza"
    assert record["email"] == "ali@example.com"
    assert record["phone"] == "+92 300 1007919"
    assert record["location"] == "Lahore, Pakistan"
    assert record["rank"] == 1
    assert record["status"] == "New"
    assert record["job_title"] == "Developer"
    assert "Python: 3 years" in record["findings_json"]


def test_only_shortlisted_candidates_are_saved():
    _, saved = save_one(requirement=skill("java"))
    assert saved == 0
    assert db.list_candidates() == []


def test_running_again_updates_and_keeps_human_notes():
    save_one()
    candidate_id = db.list_candidates()[0]["id"]
    db.update_candidate(candidate_id, status="Interview", notes="Call on Monday")
    save_one()
    records = db.list_candidates()
    assert len(records) == 1
    assert (records[0]["status"], records[0]["notes"]) == ("Interview", "Call on Monday")


# --- Create ---
def test_a_person_can_create_a_record_without_any_analysis():
    job_id = db.save_job("Accountant", "", [], "Manual")
    candidate_id = db.create_candidate(job_id, name="  Sara Khan ", email="sara@example.com", candidate_type="Student",
                                       total_years=1.5, skills="Excel", notes="Referred by a friend")
    record = db.get_candidate(candidate_id)
    assert record["name"] == "Sara Khan"
    assert record["candidate_type"] == "Student"
    assert record["decided_by"] == "Manual entry"
    assert record["match_score"] is None
    assert record["job_title"] == "Accountant"


def test_the_same_person_cannot_be_created_twice_for_a_job():
    job_id = db.save_job("Accountant", "", [], "Manual")
    db.create_candidate(job_id, name="Sara Khan", email="sara@example.com")
    with pytest.raises(ValueError, match="already saved"):
        db.create_candidate(job_id, name="S. Khan", email="SARA@example.com")


@pytest.mark.parametrize("details,message", [
    ({"name": "   "}, "enter a name"),
    ({"name": "Sara", "email": "not-an-email"}, "email"),
    ({"name": "Sara", "status": "Maybe"}, "status"),
    ({"name": "Sara", "candidate_type": "Robot"}, "candidate type"),
    ({"name": "Sara", "total_years": 99}, "between 0 and 60"),
])
def test_bad_details_are_refused_with_a_clear_message(details, message):
    job_id = db.save_job("Accountant", "", [], "Manual")
    with pytest.raises(ValueError, match=message):
        db.create_candidate(job_id, **details)
    assert db.list_candidates() == []


# --- Update ---
def test_every_detail_of_a_record_can_be_changed():
    save_one()
    candidate_id = db.list_candidates()[0]["id"]
    changes = {"name": "Ali R. Khan", "email": "new@example.com", "phone": "03009998888", "location": "Multan",
               "current_title": "Team Lead", "candidate_type": "Student", "total_years": 7.5, "education": "MS Computer Science",
               "skills": "Python, Go", "status": "Hired", "notes": "Joined"}
    db.update_candidate(candidate_id, **changes)
    record = db.get_candidate(candidate_id)
    assert {name: record[name] for name in changes} == changes


def test_changing_one_field_leaves_the_others_alone():
    save_one()
    before = db.list_candidates()[0]
    db.update_candidate(before["id"], location="Multan")
    after = db.get_candidate(before["id"])
    assert after["location"] == "Multan"
    assert (after["name"], after["email"], after["match_score"]) == (before["name"], before["email"], before["match_score"])


def test_analysis_does_not_overwrite_a_person_s_corrections():
    save_one()
    candidate_id = db.list_candidates()[0]["id"]
    db.update_candidate(candidate_id, phone="03009998888", location="Multan")
    save_one()
    record = db.get_candidate(candidate_id)
    assert len(db.list_candidates()) == 1
    assert (record["phone"], record["location"]) == ("03009998888", "Multan")


def test_analysis_still_refreshes_the_score_of_a_corrected_record():
    save_one()
    candidate_id = db.list_candidates()[0]["id"]
    db.update_candidate(candidate_id, location="Multan")
    with sqlite3.connect(database_path()) as connection:
        connection.execute("UPDATE shortlisted_candidates SET match_score = 1")
    save_one()
    assert db.get_candidate(candidate_id)["match_score"] == 100


def test_changing_only_the_status_is_not_a_correction():
    save_one()
    candidate_id = db.list_candidates()[0]["id"]
    db.update_candidate(candidate_id, status="Contacted")
    assert db.get_candidate(candidate_id)["edited_by_person"] == 0


def test_updating_a_deleted_record_is_explained():
    with pytest.raises(ValueError, match="no longer exists"):
        db.update_candidate(999, status="Hired")


# --- Older databases ---
def test_database_from_the_earlier_version_is_upgraded_and_keeps_its_records():
    save_one()
    with sqlite3.connect(database_path()) as connection:
        connection.execute("ALTER TABLE shortlisted_candidates DROP COLUMN edited_by_person")
    db.init_db()
    record = db.list_candidates()[0]
    assert record["name"] == "Ali Raza"
    assert record["edited_by_person"] == 0


def test_same_person_can_be_saved_for_two_jobs():
    save_one(title="Developer")
    save_one(title="Engineer")
    assert len(db.list_candidates()) == 2
    assert len(db.list_jobs()) == 2


def test_filters():
    save_one()
    assert len(db.list_candidates(search="Lahore")) == 1
    assert len(db.list_candidates(search="python")) == 1
    assert db.list_candidates(search="Karachi") == []
    assert db.list_candidates(status="Hired") == []
    assert db.list_candidates(candidate_type="Student") == []


def test_search_text_is_treated_as_data():
    save_one()
    assert db.list_candidates(search="'; DROP TABLE jobs; --") == []
    assert len(db.list_jobs()) == 1


def test_delete():
    save_one()
    db.delete_candidate(db.list_candidates()[0]["id"])
    assert db.list_candidates() == []


def test_unknown_status_is_refused():
    save_one()
    with pytest.raises(ValueError):
        db.update_candidate(db.list_candidates()[0]["id"], status="Maybe")


def test_deleting_a_job_removes_its_candidates():
    job_id, _ = save_one()
    other_job, _ = save_one(title="Engineer")
    db.delete_job(job_id)
    assert [job["id"] for job in db.list_jobs()] == [other_job]
    assert [record["job_id"] for record in db.list_candidates()] == [other_job]
