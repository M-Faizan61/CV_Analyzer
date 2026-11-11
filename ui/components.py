"""Small display pieces shared by the screens.

Text from CVs is untrusted, so it is always escaped before being placed in HTML.
"""
import html
import json

import streamlit as st

from models.schemas import CandidateResult, Finding

STEPS = ("Method", "Job description", "CVs", "Results")

OUTCOME_LABELS = {
    "SHORTLISTED": "Shortlisted",
    "NEEDS_REVIEW": "Needs review",
    "NOT_SHORTLISTED": "Not shortlisted",
    "FILE_ERROR": "File problem",
}
_CHECK_STYLES = {
    "MET": ("met", "✓"),
    "NOT_MET": ("not-met", "✗"),
    "REVIEW": ("review", "?"),
}
_PRIORITY_TAGS = {"mandatory": "Must have", "preferred": "Nice to have"}


def stepper(current: int) -> None:
    """Show the four steps, with the current one highlighted."""
    items = []
    for number, label in enumerate(STEPS, 1):
        state = "current" if number == current else "done" if number < current else ""
        mark = "✓ " if number < current else f"{number}. "
        items.append(f'<div class="step {state}">{mark}{label}</div>')
    st.html(f'<div class="stepper">{"".join(items)}</div>')


def safe_heading(text: str) -> None:
    """Show a name as a heading. Names can come from a CV, so they are escaped."""
    st.html(f'<div class="record-name">{html.escape(text)}</div>')


def years_text(years: float | None, source: str = "") -> str:
    if years is None:
        return ""  # shown as "Not found" or "Not added", depending on the screen
    text = f"{years:g} year" + ("" if years == 1 else "s")
    return f"{text} (from job dates)" if source == "job dates" else text


def _fact(label: str, value: str, empty: str) -> str:
    return (f'<div><div class="fact-label">{html.escape(label)}</div>'
            f'<div class="fact-value">{html.escape(value or empty)}</div></div>')


def render_facts(facts: dict[str, str], empty: str = "Not found") -> None:
    """Show label and value pairs in a tidy grid. `empty` is shown for a blank value."""
    st.html(f'<div class="facts">{"".join(_fact(label, value, empty) for label, value in facts.items())}</div>')


def render_findings(findings: list[Finding]) -> None:
    """Show each requirement with its result, reason and the CV's own words."""
    if not findings:
        return
    cards = []
    for finding in findings:
        style, mark = _CHECK_STYLES[finding.status]
        tag = _PRIORITY_TAGS.get(finding.importance, "")
        quote = f'<div class="check-quote">{html.escape(finding.evidence)}</div>' if finding.evidence else ""
        cards.append(
            f'<div class="check {style}">'
            f'<div class="check-title">{mark} {html.escape(finding.requirement)}<span class="check-tag">{tag}</span></div>'
            f'<div class="check-reason">{html.escape(finding.reason)}</div>{quote}</div>')
    st.html("".join(cards))


def result_facts(result: CandidateResult) -> dict[str, str]:
    profile = result.profile
    return {
        "Email": profile.email,
        "Phone": "; ".join(profile.phones),
        "Location": profile.location,
        "Current role": profile.current_title,
        "Experience": years_text(profile.total_years, profile.total_years_source),
        "Education": profile.education,
        "Candidate type": profile.candidate_type,
        "Skills": ", ".join(profile.skills),
        "CV file": result.source_name,
    }


def saved_facts(record: dict) -> dict[str, str]:
    return {
        "Email": record["email"],
        "Phone": record["phone"],
        "Location": record["location"],
        "Current role": record["current_title"],
        "Experience": years_text(record["total_years"]),
        "Education": record["education"],
        "Candidate type": record["candidate_type"],
        "Skills": record["skills"],
        "CV file": record["source_file"],
        "Status": record["status"],
        "Notes": record["notes"],
        "Added by": record["decided_by"],
        "Last changed": record["updated_at"].replace("T", " ")[:16],
    }


def findings_from_record(record: dict) -> list[Finding]:
    return [Finding.model_validate(item) for item in json.loads(record["findings_json"])]
