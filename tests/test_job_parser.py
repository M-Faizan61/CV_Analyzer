import pytest

from services.job_parser import guess_job_title, parse_job_locally, validate_requirements


def used(text):
    return [item for item in parse_job_locally(text) if item.importance != "ignore"]


def test_headings_and_titles_are_not_requirements():
    """These lines blocked every candidate in the old system."""
    requirements = used("WordPress Developer\nRequirements:\nPHP required")
    assert [item.text for item in requirements] == ["PHP required"]


def test_section_headings_set_the_priority():
    requirements = used("Requirements:\n- Python\nNice to have:\n- Docker")
    assert [(item.skills, item.importance) for item in requirements] == [("python", "mandatory"), ("docker", "preferred")]


def test_words_in_the_line_win_over_the_section():
    assert used("Requirements:\nDocker is a plus")[0].importance == "preferred"


def test_duties_and_company_text_are_ignored():
    text = "About us\nWe build websites.\nResponsibilities:\n- Build REST APIs with Django\n- Write clean code"
    assert used(text) == []


def test_a_job_title_inside_a_sentence_is_not_a_skill():
    assert used("We are hiring a Data Analyst in Karachi.") == []


def test_nothing_is_thrown_away():
    assert len(parse_job_locally("About us\nWe build websites.")) == 1


@pytest.mark.parametrize("line,years", [
    ("3+ years of Python", 3),
    ("At least three years of Python", 3),
    ("2-4 years of Python", 2),
    ("Python", None),
])
def test_years_are_read(line, years):
    assert used(f"Requirements:\n{line}")[0].min_years == years


def test_years_without_a_skill_mean_total_experience():
    requirement = used("Requirements:\nMinimum 3 years of experience")[0]
    assert (requirement.kind, requirement.min_years) == ("experience", 3)


def test_years_in_an_unknown_area_are_not_total_experience():
    assert used("5 years of banking experience required")[0].kind == "other"


def test_preferably_at_least_is_not_mandatory():
    requirement = used("Preferably at least three years of Python experience")[0]
    assert (requirement.importance, requirement.kind) == ("preferred", "skill")


def test_or_group_is_one_requirement():
    requirement = used("Django or Flask required")[0]
    assert (requirement.skills, requirement.operator) == ("django, flask", "ANY")


def test_named_products_narrow_a_general_skill():
    requirement = used("Database experience (MySQL, PostgreSQL) required")[0]
    assert (requirement.skills, requirement.operator) == ("mysql, postgresql", "ANY")


def test_unknown_tools_in_a_list_are_kept():
    assert used("Requirements:\nTools: Salesforce, HubSpot")[0].skills == "Salesforce, HubSpot"


@pytest.mark.parametrize("line", [
    "Build and maintain client websites",
    "Ability to work and learn quickly",
    "Attention to detail, punctuality",
])
def test_ordinary_sentences_do_not_become_fake_skills(line):
    requirement = used(f"Requirements:\n{line}")[0]
    assert (requirement.skills, requirement.importance) == ("", "preferred")


def test_soft_skills_cannot_block_everyone():
    requirement = used("Excellent communication skills required")[0]
    assert (requirement.kind, requirement.importance) == ("other", "preferred")


@pytest.mark.parametrize("line,degree,field", [
    ("Bachelor's degree in Computer Science", "bachelor", "computer science"),
    ("Master's degree required", "master", ""),
    ("BS/MS in Computer Science", "bachelor", "computer science"),
    ("Degree required", "bachelor", ""),
])
def test_degrees_are_read(line, degree, field):
    requirement = used(f"Requirements:\n{line}")[0]
    assert (requirement.kind, requirement.degree, requirement.degree_field) == ("education", degree, field)


def test_all_listed_subjects_are_kept():
    requirement = used("MS or BS in Data Science, Statistics or Computer Science required.")[0]
    assert set(requirement.degree_field.split(", ")) == {"data science", "statistics", "computer science"}


def test_job_title_suggestion():
    assert guess_job_title("Job Title: SEO Specialist\nLocation: Lahore") == "SEO Specialist"
    assert guess_job_title("WordPress Developer\nRequirements:") == "WordPress Developer"
    assert guess_job_title("We build websites for clients.") == ""


def test_repeated_lines_are_counted_once():
    assert len(parse_job_locally("Python required\nPython required")) == 1


@pytest.mark.parametrize("rows,message", [
    ([{"id": "R1", "text": "Docker", "importance": "preferred", "kind": "skill", "skills": "docker"}], "Must have"),
    ([{"id": "R1", "text": "Python", "importance": "mandatory", "kind": "skill", "skills": ""}], "skill name"),
    ([{"id": "R1", "text": "Experience", "importance": "mandatory", "kind": "experience"}], "minimum years"),
    ([{"id": "R1", "text": "Python", "importance": "mandatory", "kind": "nonsense"}], "not valid"),
])
def test_reviewed_list_is_checked(rows, message):
    with pytest.raises(ValueError, match=message):
        validate_requirements(rows)


def test_a_requirement_listed_twice_is_rejected():
    row = {"id": "R1", "text": "Python", "importance": "mandatory", "kind": "skill", "skills": "python"}
    with pytest.raises(ValueError, match="listed twice"):
        validate_requirements([row, {**row, "id": "R2"}])
