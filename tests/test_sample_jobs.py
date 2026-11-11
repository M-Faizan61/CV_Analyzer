"""Run every test job description against the sample CVs.

The expected results were worked out by hand from the CVs, not copied from the
system's output. docs/test_jobs.md explains what each job tests. If the sample
files are missing or renamed, these tests are skipped.
"""
import pytest

from config import settings
from helpers import typed_cv
from services import pipeline
from services.pipeline import CvInput

JOB_FOLDER = settings.ROOT / "data" / "job_descriptions"
CV_NAMES = ["cv_01_ali_raza", "cv_02_hamza_tariq", "cv_03_sana_malik", "cv_04_usman_khalid", "cv_05_bilal_ahmed",
            "cv_06_ayesha_noor", "cv_07_zain_abbas", "cv_08_farhan_iqbal", "cv_09_maryam_sheikh", "cv_10_hassan_javed"]
SKILLS_ONLY_CV = "Name: Ahmed Ali\nCell: 03001234567\nLocation: Lahore, Pakistan\nSkills: Python, SQL, Git\nBuilt an internal reporting tool."

# job file: (shortlisted, best first), (needs review)
EXPECTED = {
    "sample_wordpress_developer": (["Farhan Iqbal", "Bilal Ahmed", "Ayesha Noor"], []),
    "sample_python_developer": (["Hamza Tariq", "Ali Raza"], []),
    "job_01_junior_python_developer": (["Ali Raza", "Hamza Tariq", "Usman Khalid", "Sana Malik"], ["Ahmed Ali"]),
    "job_02_senior_python_developer": (["Hamza Tariq"], []),
    "job_03_django_developer": (["Ali Raza"], []),
    "job_04_backend_developer": (["Hamza Tariq", "Usman Khalid", "Ali Raza", "Sana Malik"], []),
    "job_05_full_stack_developer": ([], []),
    "job_06_java_developer": ([], []),
    "job_07_nodejs_developer": ([], []),
    "job_08_front_end_developer": (["Zain Abbas"], []),
    "job_09_data_analyst": (["Sana Malik"], []),
    "job_10_data_scientist": (["Usman Khalid"], []),
    "job_11_bi_analyst": ([], []),
    "job_12_mysql_database_developer": ([], []),
    "job_13_senior_wordpress_developer": (["Farhan Iqbal"], []),
    "job_14_wordpress_plugin_developer": ([], ["Ayesha Noor", "Bilal Ahmed", "Farhan Iqbal"]),
    "job_15_woocommerce_developer": (["Bilal Ahmed"], []),
    "job_16_elementor_web_designer": (["Ayesha Noor"], []),
    "job_17_cms_developer": (["Farhan Iqbal", "Ayesha Noor", "Bilal Ahmed", "Zain Abbas"], []),
    "job_18_seo_specialist": (["Maryam Sheikh"], []),
    "job_19_technical_seo_lead": (["Hassan Javed"], []),
    "job_20_content_writer": (["Maryam Sheikh"], []),
    "job_21_digital_marketing_executive": (["Hassan Javed", "Maryam Sheikh"], []),
    "job_22_python_intern": (["Hamza Tariq", "Usman Khalid", "Ali Raza", "Sana Malik", "Ahmed Ali"], []),
    "job_23_data_entry_operator": (["Sana Malik"], []),
    "job_24_data_analyst_paragraph": (["Sana Malik"], []),
    "job_25_team_lead": (["Farhan Iqbal", "Hamza Tariq", "Hassan Javed"], []),
    "job_26_crm_executive": ([], []),
}


@pytest.fixture(scope="module")
def sample_cvs():
    paths = [settings.CV_FOLDER / f"{name}.pdf" for name in CV_NAMES]
    if not all(path.exists() for path in paths):
        pytest.skip("The sample CVs are not in data/cvs.")
    return [CvInput(name=path.name, source="Folder", content=path.read_bytes()) for path in paths] + [typed_cv(SKILLS_ONLY_CV, "ahmed_ali.txt")]


def analyze(job_name: str, cvs: list[CvInput]):
    path = JOB_FOLDER / f"{job_name}.txt"
    if not path.exists():
        pytest.skip(f"{path.name} is not in data/job_descriptions.")
    requirements = pipeline.read_requirements(path.read_text(encoding="utf-8"))
    return requirements, pipeline.analyze_batch(cvs, requirements)


@pytest.mark.parametrize("job_name", EXPECTED)
def test_job_gives_the_expected_candidates(job_name, sample_cvs):
    _, results = analyze(job_name, sample_cvs)
    shortlisted, needs_review = EXPECTED[job_name]
    assert [r.display_name for r in results if r.outcome == "SHORTLISTED"] == shortlisted
    assert sorted(r.display_name for r in results if r.outcome == "NEEDS_REVIEW") == needs_review


def test_every_job_file_has_an_expected_result():
    if not JOB_FOLDER.exists():
        pytest.skip("No job descriptions folder.")
    assert {path.stem for path in JOB_FOLDER.glob("*.txt")} <= set(EXPECTED)


def test_equal_candidates_share_a_rank(sample_cvs):
    _, results = analyze("job_25_team_lead", sample_cvs)
    assert [(r.display_name, r.rank) for r in results if r.rank] == [("Farhan Iqbal", 1), ("Hamza Tariq", 2), ("Hassan Javed", 2)]


def test_near_miss_on_years_is_explained(sample_cvs):
    _, results = analyze("job_11_bi_analyst", sample_cvs)
    sana = next(result for result in results if result.display_name == "Sana Malik")
    assert sana.outcome == "NOT_SHORTLISTED"
    assert any("2 years" in finding.reason and "3 years" in finding.reason for finding in sana.findings)


def test_personal_conditions_are_listed_but_not_used(sample_cvs):
    requirements, results = analyze("job_23_data_entry_operator", sample_cvs)
    personal = [item.text for item in requirements if item.kind == "personal"]
    assert len(personal) == 3
    assert not any(finding.requirement in personal for result in results for finding in result.findings)


def test_candidate_without_the_named_skill_is_not_sent_to_review(sample_cvs):
    _, results = analyze("job_14_wordpress_plugin_developer", sample_cvs)
    assert next(r for r in results if r.display_name == "Ali Raza").outcome == "NOT_SHORTLISTED"
