"""Work out years of experience from a CV, using plain arithmetic.

Two sources are used, and the UI always says which one a number came from:
  * stated:     the CV says it directly, e.g. "Python: 5 years"
  * job dates:  calculated from dated jobs under the experience section
"""
import re
from dataclasses import dataclass, field
from datetime import date

from services.cv_sections import split_sections
from services.skill_matcher import accepted_skills, aliases_of, canonical, mentions_skill

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUMBER = r"(\d+(?:\.\d+)?|" + "|".join(_NUMBER_WORDS) + r")"
_YEARS = r"(?:years?|yrs?)"

_RANGE_OF_YEARS = re.compile(rf"\b{_NUMBER}\s*(?:-|–|—|to)\s*{_NUMBER}\s*\+?\s*{_YEARS}\b", re.I)
_SOME_YEARS = re.compile(rf"\b{_NUMBER}\s*\+?\s*{_YEARS}\b", re.I)
_TOTAL_LABEL = re.compile(rf"total\s+(?:\w+\s+)?experience\s*[:\-–]?\s*(?:of\s+)?{_NUMBER}\s*\+?\s*{_YEARS}\b", re.I)
_EXPERIENCE_STATEMENT = re.compile(
    rf"\b{_NUMBER}\s*\+?\s*{_YEARS}\s+(?:of\s+)?(?:(?:professional|work|working|industry|relevant|overall|total)\s+)?experience\b", re.I)

_MONTHS = {name: number for number, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{_MONTH}\s+|\d{{1,2}}[/-])?(?:19|20)\d{{2}}"
_DATE_RANGE = re.compile(
    rf"({_DATE})\s*(?:-|–|—|to|until|till)\s*({_DATE}|present|current|now|till date|to date|ongoing)", re.I)


@dataclass
class Job:
    """One dated job. Months are counted from year 0, which makes subtraction easy."""
    start: int
    end: int
    lines: list[str] = field(default_factory=list)


@dataclass
class YearsFound:
    value: float | None = None
    source: str = ""
    line: str = ""


def _to_number(value: str) -> float:
    return float(_NUMBER_WORDS.get(value.lower(), value))


def _month_index(value: str, today: date) -> int:
    """Convert "Mar 2021", "03/2021", "2021" or "Present" to a month count."""
    cleaned = value.strip().lower()
    if not re.search(r"\d{4}", cleaned):  # present, current, now ...
        return today.year * 12 + today.month
    year = int(re.search(r"(?:19|20)\d{2}", cleaned)[0])
    named = re.match(r"[a-z]{3}", cleaned)
    number = re.match(r"(\d{1,2})[/-]", cleaned)
    if named and named[0] in _MONTHS:
        month = _MONTHS[named[0]]
    elif number and 1 <= int(number[1]) <= 12:
        month = int(number[1])
    else:
        month = 1
    return year * 12 + month


def _merged_months(jobs: list[Job]) -> int:
    """Total months worked, counting overlapping jobs only once."""
    total, covered_until = 0, None
    for job in sorted(jobs, key=lambda item: item.start):
        start = job.start if covered_until is None else max(job.start, covered_until)
        if job.end > start:
            total += job.end - start
            covered_until = job.end
    return total


def find_jobs(cv_text: str, today: date | None = None) -> list[Job]:
    """Read the dated jobs from the experience section."""
    today = today or date.today()
    jobs: list[Job] = []
    for line in split_sections(cv_text).get("experience", []):
        match = _DATE_RANGE.search(line)
        if match:
            start, end = _month_index(match[1], today), _month_index(match[2], today)
            if end > start:
                jobs.append(Job(start, end, [line]))
        elif jobs:
            jobs[-1].lines.append(line)
    return jobs


def find_total_years(cv_text: str, today: date | None = None) -> YearsFound:
    """Total work experience: an explicit total wins, otherwise the best evidence available."""
    label = _TOTAL_LABEL.search(cv_text)
    if label:
        return YearsFound(_to_number(label[1]), "stated", label[0])

    stated = [_to_number(match[1]) for match in _EXPERIENCE_STATEMENT.finditer(cv_text)]
    best_stated = max(stated, default=None)
    jobs = find_jobs(cv_text, today)
    from_dates = round(_merged_months(jobs) / 12, 1) if jobs else None

    if best_stated is not None and (from_dates is None or best_stated >= from_dates):
        return YearsFound(best_stated, "stated")
    if from_dates is not None:
        return YearsFound(from_dates, "job dates")
    return YearsFound()


def _stated_skill_years(cv_text: str, skill: str) -> YearsFound:
    """Find statements such as "Python: 5 years" or "3+ years of Python"."""
    best = YearsFound()
    for line in cv_text.splitlines():
        for name in accepted_skills(skill):
            for alias in aliases_of(name):
                term = re.escape(alias)
                after = rf"(?<![\w]){term}(?![\w])\s*[:(\-–—]?\s*(?:for\s+)?{_NUMBER}\s*\+?\s*{_YEARS}\b"
                before = (rf"\b{_NUMBER}\s*\+?\s*{_YEARS}\s*(?:of\s+)?(?:(?:hands[- ]on|professional|commercial)\s+)?"
                          rf"(?:experience\s+)?(?:(?:in|with|using|on)\s+)?{term}(?![\w])")
                match = re.search(after, line, re.I) or re.search(before, line, re.I)
                if match and (best.value is None or _to_number(match[1]) > best.value):
                    best = YearsFound(_to_number(match[1]), "stated", line.strip(" \t-•*"))
    return best


def find_skill_years(cv_text: str, skill: str, today: date | None = None) -> YearsFound:
    """Years with one skill: what the CV states, otherwise an estimate from job dates."""
    skill = canonical(skill)
    stated = _stated_skill_years(cv_text, skill)
    if stated.value is not None:
        return stated

    accepted = accepted_skills(skill)
    jobs = [job for job in find_jobs(cv_text, today)
            if any(mentions_skill(line, name) for line in job.lines for name in accepted)]
    if jobs:
        return YearsFound(round(_merged_months(jobs) / 12, 1), "job dates", jobs[0].lines[0])
    return YearsFound()


def find_required_years(text: str) -> float | None:
    """Read the years a job asks for: "3+ years" -> 3, "2-4 years" -> 2."""
    match = _RANGE_OF_YEARS.search(text) or _SOME_YEARS.search(text)
    return _to_number(match[1]) if match else None
