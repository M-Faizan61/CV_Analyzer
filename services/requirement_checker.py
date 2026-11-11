"""Check one requirement against one CV.

Every result is MET, NOT_MET or REVIEW, and always carries a reason, so a person
can see why. The AI may add evidence, but this code makes the decision:
  * its quotes are accepted only if they really appear in the CV
  * it can never mark a named skill as met, because the directional skill rules
    must hold ("SQL does not prove MySQL"). It can only ask a person to look.
"""
from dataclasses import dataclass, field

from models.schemas import AiFinding, CandidateProfile, Finding, Requirement
from services.education_extractor import LEVEL_ORDER, allows_related_field, degree_label, field_matches
from services.experience_extractor import find_skill_years
from services.skill_matcher import find_skill_evidence
from services.text_utils import has_word, is_verbatim, key_terms, split_statements


@dataclass
class _Check:
    status: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    years: float | None = None


def _years_text(years: float) -> str:
    return f"{years:g} year" + ("" if years == 1 else "s")


def _check_one_skill(skill: str, requirement: Requirement, cv_text: str) -> _Check:
    found = find_skill_evidence(cv_text, skill)
    years = find_skill_years(cv_text, skill)
    check = _Check(found.status, found.reason, found.evidence, years.value)
    needed = requirement.min_years
    if found.status != "MET" or needed is None:
        return check

    if years.value is None:
        check.status = "REVIEW"
        check.reason = f"Found, but the CV does not say for how long ({_years_text(needed)} needed)."
    elif years.value >= needed:
        how = "stated in the CV" if years.source == "stated" else "estimated from job dates"
        check.reason = f"{_years_text(years.value)} ({how}), {_years_text(needed)} needed."
    elif years.source == "stated":
        check.status = "NOT_MET"
        check.reason = f"The CV states {_years_text(years.value)}, but {_years_text(needed)} are needed."
    else:
        # Job dates can miss time spent on a skill, so a low estimate is not proof.
        check.status = "REVIEW"
        check.reason = f"Job dates suggest about {_years_text(years.value)}, but {_years_text(needed)} are needed. Please check."
    if years.line:
        check.evidence = list(dict.fromkeys([years.line] + check.evidence))
    return check


def _check_skills(requirement: Requirement, cv_text: str) -> _Check:
    skills = requirement.skill_list
    checks = [_check_one_skill(skill, requirement, cv_text) for skill in skills]
    statuses = [check.status for check in checks]

    if requirement.operator == "ANY":
        status = "MET" if "MET" in statuses else "REVIEW" if "REVIEW" in statuses else "NOT_MET"
        counted = [check for check in checks if check.status == status]
    else:
        status = "NOT_MET" if "NOT_MET" in statuses else "REVIEW" if "REVIEW" in statuses else "MET"
        counted = checks

    known_years = [check.years for check in counted if check.years is not None]
    evidence = list(dict.fromkeys(line for check in checks for line in check.evidence))
    # With several skills, each reason says which skill it is about.
    reasons = [check.reason for check in checks] if len(skills) == 1 else [f"{skill}: {check.reason}" for skill, check in zip(skills, checks)]
    return _Check(status, " ".join(reasons), evidence, max(known_years, default=None))


def _check_experience(requirement: Requirement, profile: CandidateProfile) -> _Check:
    needed = requirement.min_years or 0
    total = profile.total_years
    if total is None:
        if profile.has_experience_section:
            return _Check("REVIEW", "The CV lists work experience, but its length could not be worked out.")
        return _Check("NOT_MET", "The CV does not show any work experience.")
    how = "stated in the CV" if profile.total_years_source == "stated" else "calculated from job dates"
    if total >= needed:
        return _Check("MET", f"{_years_text(total)} of experience ({how}), {_years_text(needed)} needed.", years=total)
    return _Check("NOT_MET", f"{_years_text(total)} of experience ({how}), but {_years_text(needed)} are needed.", years=total)


def _check_education(requirement: Requirement, profile: CandidateProfile) -> _Check:
    needed = degree_label(requirement.degree)
    if not profile.degrees:
        return _Check("NOT_MET", f"No degree found in the CV ({needed} needed).")

    required_level = LEVEL_ORDER.get(requirement.degree, 0)
    high_enough = [degree for degree in profile.degrees if LEVEL_ORDER.get(degree.level, 0) >= required_level]
    if not high_enough:
        return _Check("NOT_MET", f"Highest degree found is below the {needed} needed.", [d.text for d in profile.degrees])

    finished = [degree for degree in high_enough if not degree.in_progress]
    if not finished:
        return _Check("REVIEW", f"This degree is still in progress ({needed} needed).", [d.text for d in high_enough])

    subject = requirement.degree_field
    if not subject:
        return _Check("MET", f"{needed} found.", [finished[0].text])
    matching = [degree for degree in finished if field_matches(degree.text, subject)]
    if matching:
        return _Check("MET", f"{needed} in a matching subject found.", [matching[0].text])
    if allows_related_field(requirement.text):
        return _Check("REVIEW", f"Degree found, but please check whether its subject is related to {subject}.", [finished[0].text])
    return _Check("NOT_MET", f"Degree found, but not in {subject}.", [finished[0].text])


def _check_other(requirement: Requirement, cv_text: str) -> _Check:
    """Free-text requirements: look for all the key words together in one statement."""
    # "WordPress plugin development" cannot be met if the CV never shows WordPress.
    if requirement.skill_list:
        named_skills = _check_skills(requirement, cv_text)
        if named_skills.status == "NOT_MET":
            return named_skills

    terms = key_terms(requirement.text)
    if terms:
        for statement in split_statements(cv_text):
            if all(has_word(statement, term) for term in terms):
                if requirement.min_years is None:
                    return _Check("MET", "The key words of this requirement appear together in the CV.", [statement])
                return _Check("REVIEW", "Related wording found. Please check the years.", [statement])
    return _Check("REVIEW", "Rules cannot confirm this one. Please read the CV, or use the AI method.")


def _apply_ai(check: _Check, requirement: Requirement, ai_finding: AiFinding, cv_text: str) -> _Check:
    """Combine the rule result with what the AI found."""
    quote_is_real = is_verbatim(ai_finding.quote, cv_text)
    named_skill_missing = bool(requirement.skill_list) and check.status == "NOT_MET"

    if requirement.kind == "other" and not named_skill_missing:
        if ai_finding.answer == "not_found":
            return _Check("NOT_MET", "The AI read the CV and found no evidence for this.")
        if ai_finding.answer == "found" and quote_is_real:
            return _Check("MET", "The AI found this, and its quote was checked against the CV.", [ai_finding.quote.strip()])
        if ai_finding.answer == "found":
            return _Check("REVIEW", "The AI claimed evidence, but its quote is not in the CV. Please check.")
        evidence = [ai_finding.quote.strip()] if quote_is_real else []
        return _Check("REVIEW", "The AI found this unclear. Please read the CV.", evidence)

    # Named skills, years and degrees: rules decide. The AI can only request a human check.
    if check.status != "MET" and ai_finding.answer == "found" and quote_is_real:
        return _Check("REVIEW", f"{check.reason} The AI thinks this line may count. Please check.",
                      list(dict.fromkeys(check.evidence + [ai_finding.quote.strip()])), check.years)
    return check


def check_requirement(requirement: Requirement, profile: CandidateProfile, cv_text: str, ai_finding: AiFinding | None = None) -> Finding:
    """Run the right check for this kind of requirement."""
    if requirement.kind == "skill" and requirement.skill_list:
        check = _check_skills(requirement, cv_text)
    elif requirement.kind == "experience":
        check = _check_experience(requirement, profile)
    elif requirement.kind == "education":
        check = _check_education(requirement, profile)
    else:
        check = _check_other(requirement, cv_text)

    if ai_finding is not None:
        check = _apply_ai(check, requirement, ai_finding, cv_text)

    return Finding(
        requirement_id=requirement.id,
        requirement=requirement.text,
        importance=requirement.importance,
        kind=requirement.kind,
        status=check.status,
        evidence="\n".join(check.evidence),
        reason=check.reason,
        years=check.years,
    )
