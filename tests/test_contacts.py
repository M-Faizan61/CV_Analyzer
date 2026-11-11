from services.contact_extractor import extract_contact
from services.cv_parser import build_profile
from services.experience_extractor import find_total_years
from datetime import date


def test_labelled_contact_and_reference_exclusion():
    result = extract_contact("Full Name: Ahmed Ali\nCell No: +92 300 1234567\nLocation: Lahore, Pakistan\nSkills: SQL\nReferences\nName: Other Person\nPhone: 03009876543")
    assert result["name"] == "Ahmed Ali"
    assert result["phones"] == ["+92 300 1234567"]
    assert result["location"] == "Lahore, Pakistan"


def test_heading_and_pipe_contacts():
    result = extract_contact("CV\nAyesha Khan\nMobile: 0300-1234567 | City: Karachi\nExperience\nLocation: Islamabad")
    assert result["name"] == "Ayesha Khan"
    assert result["location"] == "Karachi"
    assert result["phones"] == ["0300-1234567"]


def test_sample_cv_header():
    """The layout of the sample CVs: the location has no label."""
    result = extract_contact("Hamza Tariq\nPython Developer\nhamza.tariq@example.com | +92 300 1015838 | Karachi, Pakistan\nPROFESSIONAL SUMMARY\nText")
    assert result["name"] == "Hamza Tariq"
    assert result["email"] == "hamza.tariq@example.com"
    assert result["phones"] == ["+92 300 1015838"]
    assert result["location"] == "Karachi, Pakistan"
    assert result["current_title"] == "Python Developer"


def test_not_inferred_from_role_or_ids():
    result = extract_contact("Software Engineer\nCNIC: 35202-1234567-1\n2019-2024\nSkills: Python\nEmployer: Lahore")
    assert result["name"] == ""
    assert result["phones"] == []
    assert result["location"] == ""


def test_conflicting_values_are_not_guessed():
    result = extract_contact("Name: Ahmed Ali\nLocation: Lahore\nLocation: Karachi\nPhone: +44 7700 900123\nMobile: 03001234567\nCell: 0300-1234567")
    assert result["location"] == ""
    assert len(result["phones"]) == 2
    assert result["warnings"]


def test_referee_email_is_not_the_candidate():
    assert extract_contact("Ahmed Ali\nSkills: SQL\nReferences\nboss@example.com")["email"] == ""


def test_total_experience_prefers_the_stated_total():
    cv = "Total Experience: 5 years\nWORK EXPERIENCE\nDeveloper (2024 - 2025)"
    assert find_total_years(cv).value == 5


def test_total_experience_from_dates_counts_overlaps_once():
    cv = "WORK EXPERIENCE\nDeveloper (Jan 2018 - Jan 2021)\nConsultant (Jan 2020 - Jan 2022)"
    found = find_total_years(cv)
    assert (found.value, found.source) == (4, "job dates")


def test_education_dates_are_not_work_experience():
    assert find_total_years("EDUCATION\nBS Computer Science (2016 - 2020)").value is None


def test_present_is_today():
    cv = "WORK EXPERIENCE\nDeveloper (2020 - Present)"
    assert find_total_years(cv, today=date(2026, 1, 15)).value == 6


def test_candidate_type():
    assert build_profile("Ali Raza\nFinal year student of BS Computer Science")[0].candidate_type == "Student"
    assert build_profile("Ali Raza\nTotal Experience: 5 years")[0].candidate_type == "Employee"
    assert build_profile("Ali Raza\nSkills: Python and SQL")[0].candidate_type == "Not clear"
