"""Find degrees in a CV and in job requirements."""
import re

from models.schemas import DegreeInfo
from services.cv_sections import split_sections
from services.skill_matcher import TAXONOMY
from services.text_utils import contains, remove_term

# Higher number = higher degree. A master's satisfies a bachelor's requirement.
LEVEL_ORDER = {"diploma": 1, "bachelor": 2, "master": 3, "phd": 4}
_LABELS = {"diploma": "Diploma", "bachelor": "Bachelor's degree", "master": "Master's degree", "phd": "PhD"}

# Short forms are case sensitive, so "ms" or "ba" inside normal text is not a degree.
_NOT_A_DEGREE = r"(?!\s+(?:Office|Excel|Word|SQL|Access|Project|Teams|PowerPoint|Outlook|Azure))"
_LEVEL_PATTERNS = {
    "phd": [re.compile(r"\b(?:ph\.?\s?d|doctorate|doctor of philosophy)\b", re.I)],
    "master": [
        re.compile(r"\b(?:masters?|master['’]s|postgraduate|post[- ]graduate|m\.?phil)\b", re.I),
        re.compile(rf"(?<![A-Za-z])(?:MS{_NOT_A_DEGREE}|M\.S\.?|MSc|M\.Sc\.?|MCS|MBA|MSCS|MSSE|MSIT|MA|M\.A\.?|M\.?Tech|MEng)(?![A-Za-z])"),
    ],
    "bachelor": [
        re.compile(r"\b(?:bachelors?|bachelor['’]s)\b", re.I),
        re.compile(r"(?<![A-Za-z])(?:BS|B\.S\.?|BSc|B\.Sc\.?|BSCS|BSSE|BSIT|BCS|BBA|B\.?Com|BE|B\.E\.?|B\.?Tech|BEng|BA|B\.A\.?)(?![A-Za-z])"),
    ],
    "diploma": [re.compile(r"\b(?:diploma|associate degree|DAE)\b", re.I)],
}
# Used only when no level is named, so "Master's degree" is not read as a bachelor's.
_GENERIC_DEGREE = re.compile(r"\b(?:graduate|graduation|(?:university )?degree)\b", re.I)
_IN_PROGRESS = re.compile(r"\b(?:in progress|ongoing|expected|currently|pursuing|final year|semester|enrolled)\b", re.I)
_DEGREE_FIELD = re.compile(r"\b(?:in|of)\s+([A-Za-z][A-Za-z &]+?)(?:\s+or\b|\s+and\b|,|\.|\(|$)")
_FLEXIBLE_FIELD = re.compile(r"\b(?:related|relevant|equivalent|similar)\b", re.I)


def levels_in(line: str) -> list[str]:
    """All degree levels mentioned in a line, highest first."""
    levels = [level for level, patterns in _LEVEL_PATTERNS.items() if any(p.search(line) for p in patterns)]
    if not levels and _GENERIC_DEGREE.search(line):
        return ["bachelor"]
    return levels


def degree_label(level: str) -> str:
    return _LABELS.get(level, "Degree")


def find_degrees(cv_text: str) -> list[DegreeInfo]:
    """Read degrees from the education section, or the whole CV if there is none."""
    lines = split_sections(cv_text).get("education") or cv_text.splitlines()
    degrees = []
    for line in lines:
        levels = levels_in(line)
        if levels:
            degrees.append(DegreeInfo(level=levels[0], text=line.strip(" \t-•*"), in_progress=bool(_IN_PROGRESS.search(line))))
    return degrees


def find_required_degree(line: str) -> tuple[str, str]:
    """Read a job line. Returns (lowest accepted level, field of study), or ("", "")."""
    levels = levels_in(line)
    if not levels:
        return "", ""
    known_fields = {term for group in TAXONOMY["degree_fields"].values() for term in group}
    fields, remaining = [], line
    for term in sorted(known_fields, key=len, reverse=True):
        if contains(remaining, term):
            fields.append(term)
            remaining = remove_term(remaining, term)
    if fields:
        return levels[-1], ", ".join(fields)
    match = _DEGREE_FIELD.search(line)
    return levels[-1], match[1].strip() if match else ""


def allows_related_field(requirement_text: str) -> bool:
    return bool(_FLEXIBLE_FIELD.search(requirement_text))


def _related_fields(fields: str) -> set[str]:
    """The listed fields plus those grouped with them, e.g. CS with software engineering."""
    terms = set()
    for field in fields.split(","):
        cleaned = field.strip().lower()
        terms.add(cleaned)
        for key, group in TAXONOMY["degree_fields"].items():
            if cleaned == key or cleaned in group:
                terms.update(group)
                terms.add(key)
    return terms


def field_matches(degree_text: str, fields: str) -> bool:
    return any(contains(degree_text, term) for term in _related_fields(fields))
