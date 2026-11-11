"""Combine the extractors into one profile for a candidate.

build_profile works without any API. In the AI method, apply_ai_profile then fills
in what the rules missed, but only with values that really appear in the CV.
"""
import re

from config.settings import load_prompt
from models.schemas import CandidateProfile, CvExtraction, DegreeInfo, Requirement
from services.contact_extractor import extract_contact
from services.cv_sections import split_sections
from services.education_extractor import find_degrees, levels_in
from services.experience_extractor import find_total_years
from services.openrouter_client import request_json
from services.skill_matcher import find_skills
from services.text_utils import is_verbatim

_STUDENT_WORDS = re.compile(r"\b(?:student|undergraduate|final[- ]year|fresh graduate|fresher|currently enrolled|expected graduation)\b", re.I)


def _candidate_type(text: str, total_years: float | None, has_experience_section: bool) -> str:
    """Student or Employee, for filtering only. It never affects the decision."""
    if _STUDENT_WORDS.search(text) and not total_years:
        return "Student"
    if total_years or has_experience_section:
        return "Employee"
    return "Not clear"


def build_profile(cv_text: str) -> tuple[CandidateProfile, list[str]]:
    """Extract everything the rules can find. Returns the profile and any warnings."""
    contact = extract_contact(cv_text)
    total = find_total_years(cv_text)
    has_experience_section = bool(split_sections(cv_text).get("experience"))

    profile = CandidateProfile(
        name=contact["name"],
        email=contact["email"],
        phones=contact["phones"],
        location=contact["location"],
        current_title=contact["current_title"],
        candidate_type=_candidate_type(cv_text, total.value, has_experience_section),
        total_years=total.value,
        total_years_source=total.source,
        has_experience_section=has_experience_section,
        degrees=find_degrees(cv_text),
        skills=find_skills(cv_text),
    )
    return profile, contact["warnings"]


def extract_with_ai(cv_text: str, requirements: list[Requirement], api_key: str = "", model: str = "") -> CvExtraction:
    """Ask the AI to read one CV. Only the id and wording of each requirement are sent."""
    data = {"cv": cv_text, "requirements": [{"id": item.id, "text": item.text} for item in requirements]}
    return request_json(CvExtraction, load_prompt("extract_cv.txt"), data, api_key, model)


def apply_ai_profile(profile: CandidateProfile, extraction: CvExtraction, cv_text: str) -> CandidateProfile:
    """Use AI values only where the rules found nothing and the CV contains the value."""
    def checked(value: str) -> str:
        return value.strip() if is_verbatim(value, cv_text) else ""

    degrees = profile.degrees or [
        DegreeInfo(level=levels_in(line)[0], text=line) for line in map(checked, extraction.education) if line and levels_in(line)]
    phone = checked(extraction.phone)
    ai_skills = [skill.lower() for skill in map(checked, extraction.skills) if skill]

    return profile.model_copy(update={
        "name": profile.name or checked(extraction.name),
        "email": profile.email or checked(extraction.email),
        "phones": profile.phones or ([phone] if phone else []),
        "location": profile.location or checked(extraction.location),
        "current_title": profile.current_title or checked(extraction.current_title),
        "degrees": degrees,
        "skills": list(dict.fromkeys(profile.skills + ai_skills)),
        "summary": extraction.summary.strip(),
    })
