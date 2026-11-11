"""Find who the candidate is: name, email, phone, location and current job title.

These details are for display and for contacting people. They never affect the
decision or the ranking. The search stays inside the CV header, so employers and
referees further down are not mistaken for the candidate.
"""
import re

from services.cv_sections import heading_of

_MAX_HEADER_LINES = 15
_OTHER_PERSON = re.compile(r"\b(?:emergency contact|father'?s? name|mother'?s? name|guardian)\b", re.I)
_SECTION_START = re.compile(
    r"^(?:professional\s+)?(?:summary|profile|objective|skills|technical skills|experience|work experience"
    r"|employment|education|projects|certifications|references|referees)\b", re.I)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])(?:\+\d{1,3}[ .-]?)?(?:\(?\d{2,5}\)?[ .-]?){2,5}\d{2,4}(?![\w])")
_PHONE_LABEL = re.compile(
    r"\b(?:mobile|cell(?:\s*(?:phone|no\.?|number))?|phone|telephone|tel|contact\s*(?:no\.?|number)|whatsapp)\s*[:.\-]?\s*", re.I)
_NOT_A_PHONE = re.compile(r"\b(?:cnic|passport|national id|date of birth|dob|fax)\b", re.I)

_NAME_LABEL = re.compile(r"^(?:(?:full|candidate)\s+)?name\s*[:\-]\s*(.+)$", re.I)
_LOCATION_LABEL = re.compile(r"^(?:(?:current|residential|home)\s+)?(?:location|address|city|based in)\s*[:\-]\s*(.+)$", re.I)
# "City, Country" on the same line as an email or phone number, e.g. "Karachi, Pakistan".
_CITY_COUNTRY = re.compile(r"^[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)*,\s*[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)*$")

_JOB_WORDS = (r"engineer|developer|manager|designer|analyst|consultant|specialist|officer|intern|scientist"
              r"|administrator|architect|programmer|writer|marketer|executive|accountant|teacher|student")
_TITLE = re.compile(rf"\b(?:{_JOB_WORDS})\b", re.I)
_NOT_A_NAME = re.compile(
    rf"\b(?:resume|curriculum|vitae|cv|{_JOB_WORDS}|senior|junior|contact|email|phone|mobile|address|location"
    r"|portfolio|linkedin|github|skills|software|solutions|technologies|limited|ltd)\b", re.I)


def _plausible_name(value: str) -> bool:
    words = value.split()
    return (2 <= len(words) <= 5 and len(value) <= 80 and not _NOT_A_NAME.search(value)
            and all(char.isalpha() or char in " .'-’" for char in value)
            and all(any(char.isalpha() for char in word) for word in words))


def _header_lines(text: str) -> list[str]:
    """The lines at the top of the CV, before the first real section starts."""
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _SECTION_START.match(line) or _OTHER_PERSON.search(line):
            break
        lines.append(line)
        if len(lines) >= _MAX_HEADER_LINES:
            break
    return lines


def _single_value(values: list[str], label: str, warnings: list[str]) -> str:
    """Use a value only when the CV is consistent about it."""
    unique = {value.casefold(): value for value in values}
    if len(unique) == 1:
        return next(iter(unique.values()))
    if len(unique) > 1:
        warnings.append(f"Conflicting {label} values in the CV. Please check it.")
    return ""


def _find_phones(segments: list[str]) -> list[str]:
    phones, seen = [], set()
    for segment in segments:
        if _NOT_A_PHONE.search(segment):
            continue
        labelled = _PHONE_LABEL.search(segment)
        for match in _PHONE.finditer(segment):
            value = match[0].strip()
            digits = re.sub(r"\D", "", value)
            if not 7 <= len(digits) <= 15 or digits in seen:
                continue
            # Without a label, only trust international or Pakistan mobile formats.
            if not labelled and not (value.startswith("+") or re.fullmatch(r"03\d{9}", digits)):
                continue
            seen.add(digits)
            phones.append(value)
    return phones


def _find_email(segments: list[str], text: str) -> str:
    for segment in segments:
        match = _EMAIL.search(segment)
        if match:
            return match[0]
    # Some CVs put contact details at the end. Referee emails must not be picked up.
    before_references = re.split(r"(?im)^\s*(?:references?|referees)\b", text)[0]
    match = _EMAIL.search(before_references)
    return match[0] if match else ""


def _find_title(segments: list[str], name: str) -> str:
    for segment in segments:
        if segment != name and _TITLE.search(segment) and not re.search(r"[@\d:]", segment) and len(segment) <= 60:
            return segment
    return ""


def extract_contact(text: str) -> dict:
    """Return the candidate's contact details. A missing value is left empty."""
    warnings: list[str] = []
    lines = _header_lines(text)
    segments = [part.strip() for line in lines for part in re.split(r"[|•]|\s{3,}", line) if part.strip()]

    names = [m[1].strip() for m in map(_NAME_LABEL.match, segments) if m and _plausible_name(m[1].strip())]
    locations = [m[1].strip() for m in map(_LOCATION_LABEL.match, segments) if m and m[1].strip()]

    if not names:
        # Only the very first heading may be an unlabelled name, not text further down.
        headings = [s for s in segments if not heading_of(s) and not re.fullmatch(r"(?:resume|cv|curriculum vitae)", s, re.I)]
        if headings and _plausible_name(headings[0]):
            names.append(headings[0])

    if not locations:
        for line in lines:
            parts = [part.strip() for part in re.split(r"[|•]|\s{3,}", line)]
            if len(parts) > 1 and (_EMAIL.search(line) or _PHONE.search(line)):
                locations += [part for part in parts if _CITY_COUNTRY.fullmatch(part)]

    name = _single_value(names, "name", warnings)
    return {
        "name": name,
        "email": _find_email(segments, text),
        "phones": _find_phones(segments),
        "location": _single_value(locations, "location", warnings),
        "current_title": _find_title(segments, name),
        "warnings": warnings,
    }
