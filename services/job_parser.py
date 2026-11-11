"""Turn a job description into a list of requirements.

There are two ways to do this:
  * parse_job_locally: rules only, nothing leaves this computer (Manual method)
  * parse_job_with_ai: OpenRouter reads the text (AI method)

Both return the same Requirement objects, and the user reviews them before any CV
is analyzed. Nothing is thrown away: lines that are not requirements stay visible
with the priority "ignore", and the user can switch them on.
"""
import re

from pydantic import ValidationError

from config.settings import MAX_TEXT_CHARS, load_prompt
from models.schemas import Requirement, RequirementExtraction
from services.education_extractor import find_required_degree
from services.experience_extractor import find_required_years
from services.openrouter_client import OpenRouterError, request_json
from services.skill_matcher import SOFT_SKILLS, canonical, children_of, find_skills
from services.text_utils import is_verbatim, key_terms

# --- Words that show how important a line is ---
_PREFERRED_WORDS = re.compile(r"\b(?:prefer\w*|desirable|nice[- ]to[- ]have|good[- ]to[- ]have|a plus|bonus|advantage\w*|optional)\b", re.I)
_MANDATORY_WORDS = re.compile(r"\b(?:must|required|requires?|mandatory|essential|minimum)\b", re.I)

# --- Section headings. A heading sets the priority for the lines below it ---
_SECTIONS = {
    "preferred": r"(?:preferred|desirable|nice[- ]to[- ]have|good[- ]to[- ]have|bonus|additional|optional)(?: skills| qualifications| points?| requirements?)?",
    "info": r"(?:job |role |key |main |your |the )*(?:responsibilit(?:y|ies)|duties|description|overview|summary|about(?: us| the (?:role|company|job))?"
            r"|what you(?:'ll| will) do|benefits|perks|what we offer|we offer|compensation|salary|how to apply|company)",
    "required": r"(?:key |main |minimum |basic |job |essential |must[- ]have |technical |required |our )*"
                r"(?:requirements?|qualifications?|skills(?: required)?|required|must[- ]haves?|what we need|what you need|what you(?:'ll| will) need"
                r"|what we(?:'re| are) looking for|who you are|essentials?|mandatory|eligibility(?: criteria)?|competenc(?:y|ies))"
                r"(?: and qualifications?)?",
}
_MAX_HEADING_WORDS = 6

# --- Lines that describe the job rather than the person ---
_JOB_INFO_LABEL = re.compile(r"^(?:job title|position|role|title|company|organi[sz]ation|location|city|salary|pay|job type|type"
                             r"|department|industry|openings|vacancies|deadline|apply|timing|shift|contact)\s*[:\-–]", re.I)
_ROLE_ENDING = re.compile(r"\b(?:developer|engineer|manager|designer|analyst|specialist|scientist|administrator|consultant|officer"
                          r"|intern|executive|assistant|architect|lead|programmer|writer|marketer|operator)s?$", re.I)
_MAX_TITLE_WORDS = 7
# Job titles that contain a skill word. "We are hiring a Data Analyst" does not ask for data analysis.
_TITLE_PHRASES = re.compile(r"\b(?:data analyst|web developer|software developer|content writer|project manager)s?\b", re.I)

# --- Lines the rules should not decide alone ---
_PERSONAL = re.compile(r"\b(?:age|aged|years old|male|female|gender|domicile|nationality|marital|married|unmarried|religion|citizenship)\b", re.I)
_ACTIVITY = re.compile(r"\b(?:plugins?|themes?|modules?|extensions?|optimi[sz]ation|optimi[sz]ing|migration|architecture|automation|administration"
                       r"|certifi\w*|advanced|expert|fluent|native|mentoring)\b", re.I)
_BULLET = re.compile(r"^\s*(?:[-•*·–—▪●◦]+|\d{1,2}[.)])\s+")


def _split_lines(text: str) -> list[str]:
    lines = []
    for part in re.split(r"\n|;|(?<=[.!?])\s+(?=[A-Z])", text):
        line = _BULLET.sub("", part).strip(" \t*#")
        if line:
            lines.append(line)
    return lines


def _section_of(line: str) -> str | None:
    cleaned = line.strip(" :*#-–—").lower()
    if len(cleaned.split()) > _MAX_HEADING_WORDS:
        return None
    for section, pattern in _SECTIONS.items():
        if re.fullmatch(pattern, cleaned):
            return section
    return None


def _is_job_info(line: str) -> bool:
    if _JOB_INFO_LABEL.match(line):
        return True
    cleaned = line.rstrip(" .:!")
    return (bool(_ROLE_ENDING.search(cleaned)) and len(cleaned.split()) <= _MAX_TITLE_WORDS
            and find_required_years(line) is None and not _MANDATORY_WORDS.search(line))


def _importance_of(line: str, section: str | None) -> str | None:
    """Words in the line win over its section. None means there is no signal."""
    if _PREFERRED_WORDS.search(line):
        return "preferred"
    if _MANDATORY_WORDS.search(line):
        return "mandatory"
    return {"preferred": "preferred", "required": "mandatory", "info": "ignore"}.get(section)


def _operator_of(line: str) -> str:
    return "ANY" if re.search(r"\b(?:or|either|any of|one of)\b", line, re.I) else "ALL"


def _listed_names(line: str) -> list[str]:
    """Read a plain list of names the taxonomy does not know, e.g. "Tools: Salesforce, HubSpot"."""
    body = line.split(":", 1)[-1].strip()
    body = re.sub(r"^(?:experience|knowledge|familiarity|proficiency|expertise)\s+(?:with|in|of)\s+", "", body, flags=re.I)
    parts = [part.strip(" .") for part in re.split(r",|\band\b|\bor\b|&", body)]
    parts = [part for part in parts if part]
    # Product names are capitalised, which keeps ordinary sentences out of the list.
    if len(parts) >= 2 and all(len(part.split()) <= 3 and part[0].isupper() for part in parts):
        return parts
    return []


def _hard_skills(line: str) -> tuple[list[str], str]:
    """The skills in a line, and how they combine."""
    skills = [skill for skill in find_skills(_TITLE_PHRASES.sub(" ", line)) if skill not in SOFT_SKILLS]
    operator = _operator_of(line)
    # "Database experience (MySQL, PostgreSQL)": the named products are the examples.
    parents = [skill for skill in skills if any(child in skills for child in children_of(skill))]
    if parents:
        skills = [skill for skill in skills if skill not in parents]
        operator = "ANY"
    return skills, operator


def _parse_line(line: str, section: str | None) -> Requirement:
    """Work out what one job line is asking for."""
    if _is_job_info(line):
        return Requirement(text=line, importance="ignore")
    if _PERSONAL.search(line):
        return Requirement(text=line, importance="ignore", kind="personal")

    importance = _importance_of(line, section)
    degree, degree_field = find_required_degree(line)
    if degree:
        return Requirement(text=line, importance=importance or "mandatory", kind="education", degree=degree, degree_field=degree_field)

    min_years = find_required_years(line)
    skills, operator = _hard_skills(line)
    if skills:
        # "and" with "or" (nested logic) or a named activity needs more than a skill match.
        nested = bool(re.search(r"\band\b", line, re.I)) and operator == "ANY" and len(skills) > 2
        kind = "other" if nested or _ACTIVITY.search(line) else "skill"
        return Requirement(text=line, importance=importance or "mandatory", kind=kind,
                           skills=", ".join(skills), operator=operator, min_years=min_years)

    if min_years is not None:
        kind = "other" if key_terms(line) else "experience"
        return Requirement(text=line, importance=importance or "mandatory", kind=kind, min_years=min_years)

    listed = _listed_names(line)
    if listed and importance in ("mandatory", "preferred"):
        return Requirement(text=line, importance=importance, kind="skill", skills=", ".join(listed), operator=_operator_of(line))

    # Soft skills and free text cannot be proven by rules, so they must not block everyone.
    return Requirement(text=line, importance="ignore" if importance in (None, "ignore") else "preferred", kind="other")


def _with_ids(requirements: list[Requirement]) -> list[Requirement]:
    """Remove repeated lines and give each requirement a simple id."""
    unique = {requirement.text.casefold(): requirement for requirement in reversed(requirements)}
    ordered = list(reversed(unique.values()))
    return [requirement.model_copy(update={"id": f"R{number}"}) for number, requirement in enumerate(ordered, 1)]


def _check_length(text: str) -> None:
    if not text.strip():
        raise ValueError("Please enter a job description.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("This job description is too long.")


def parse_job_locally(text: str) -> list[Requirement]:
    """Read a job description line by line using rules only."""
    _check_length(text)
    requirements, section = [], None
    for line in _split_lines(text):
        heading = _section_of(line)
        if heading:
            section = heading
        else:
            requirements.append(_parse_line(line, section))
    return _with_ids(requirements)


def parse_job_with_ai(text: str, api_key: str = "", model: str = "") -> list[Requirement]:
    """Read a job description with OpenRouter, then apply the same safety rules."""
    _check_length(text)
    reply = request_json(RequirementExtraction, load_prompt("extract_job.txt"), {"job_description": text}, api_key, model)
    if not reply.requirements:
        raise OpenRouterError("The AI found no requirements in this job description.")

    requirements = []
    for item in reply.requirements:
        updates = {"skills": ", ".join(canonical(skill) for skill in item.skill_list)}
        if item.kind == "personal" or _PERSONAL.search(item.text):
            updates.update(kind="personal", importance="ignore")
        elif not is_verbatim(item.text, text):
            updates["importance"] = "ignore"  # a line the job does not contain must not decide anything
        requirements.append(item.model_copy(update=updates))
    return _with_ids(requirements)


def guess_job_title(text: str) -> str:
    """Suggest a title: a "Job Title: X" line, or a first line that names a role."""
    for line in _split_lines(text)[:5]:
        match = re.match(r"^(?:job title|position|role|title)\s*[:\-–]\s*(.+)$", line, re.I)
        if match:
            return match[1].strip()
    lines = _split_lines(text)
    if lines and _ROLE_ENDING.search(lines[0].rstrip(" .:!")) and len(lines[0].split()) <= _MAX_TITLE_WORDS:
        return lines[0].rstrip(" .:!")
    return ""


def validate_requirements(rows: list[dict]) -> list[Requirement]:
    """Check a reviewed list before analysis starts. Raises ValueError with a clear message."""
    try:
        requirements = [Requirement.model_validate(row) for row in rows]
    except ValidationError:
        raise ValueError("Some values in the table are not valid. Please check each row.") from None

    active =[item for item in requirements if item.importance != "ignore" and item.kind != "personal"]
    if not any(item.importance == "mandatory" for item in active):
        raise ValueError("Mark at least one requirement as Must have.")

    seen = set()
    for item in active:
        if item.kind == "skill" and not item.skill_list:
            raise ValueError(f"Add a skill name for: {item.text}")
        if item.kind == "experience" and item.min_years is None:
            raise ValueError(f"Add the minimum years for: {item.text}")
        signature = (item.text.casefold(), item.skills.casefold(), item.min_years)
        if signature in seen:
            raise ValueError(f"This requirement is listed twice: {item.text}")
        seen.add(signature)
    return requirements
