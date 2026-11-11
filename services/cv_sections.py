"""Split a CV into named sections such as skills, experience and education.

Knowing the section matters: dates under EDUCATION are not work experience, and
"MS" under SKILLS is more likely Microsoft than a master's degree.
"""
import re

# Checked in this order. "skills" comes first so that a heading like
# "SKILLS AND YEARS OF EXPERIENCE" is not treated as work experience.
_HEADINGS = {
    "skills": r"(?:technical |key |core |professional )?skills(?: .*)?|technologies|tools",
    "other": r"total experience|references?|referees|languages?|hobbies|interests|awards|achievements|publications",
    "experience": r"(?:work |working |professional |employment |relevant |industry |career )?(?:experience|history)|employment",
    "education": r"education(?:al)?(?: background| qualifications?)?|academics?(?: background)?|qualifications?",
    "summary": r"(?:professional |career )?(?:summary|profile|objective)|about me",
    "projects": r"(?:academic |personal |key |final year )?projects?",
    "certifications": r"certifications?|certificates|licen[sc]es",
}
_MAX_HEADING_WORDS = 6


def heading_of(line: str) -> str | None:
    """Return the section name if this line is a heading, otherwise None."""
    cleaned = line.strip(" \t:-–—•*#").lower()
    if not cleaned or len(cleaned.split()) > _MAX_HEADING_WORDS:
        return None
    for section, pattern in _HEADINGS.items():
        if re.fullmatch(pattern, cleaned):
            return section
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    """Group the lines of a CV by section. Lines before the first heading are "header"."""
    sections: dict[str, list[str]] = {}
    current = "header"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section = heading_of(line)
        if section:
            current = section
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return sections
