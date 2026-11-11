"""Turn the findings for each CV into a decision, a score and a ranking.

The rules, in order:
  1. Must-have requirements are gates. Nice-to-haves can never make up for a gap.
  2. A gate with no evidence -> Not shortlisted. A gate someone must read -> Needs review.
  3. Only shortlisted candidates are ranked, by the same rules for everyone.
  4. Name, phone, location, CV length and repeated keywords play no part.
  5. Equal candidates stay tied. Their rank is shared.
"""
from config.settings import load_json_config
from models.schemas import CandidateProfile, CandidateResult, Finding

SCORING = load_json_config("scoring.json")
RULES_VERSION = SCORING["version"]


def coverage(findings: list[Finding], importance: str) -> float | None:
    """Percent of these requirements that are met. Unknowns stay in the total."""
    relevant = [finding for finding in findings if finding.importance == importance]
    if not relevant:
        return None
    met = sum(finding.status == "MET" for finding in relevant)
    return round(100 * met / len(relevant), 1)


def decide_outcome(findings: list[Finding]) -> str:
    must_haves = [finding.status for finding in findings if finding.importance == "mandatory"]
    if "NOT_MET" in must_haves:
        return "NOT_SHORTLISTED"
    if "REVIEW" in must_haves:
        return "NEEDS_REVIEW"
    return "SHORTLISTED"


def match_score(mandatory: float | None, preferred: float | None) -> float:
    """Combine both coverages. If one group is empty, the other counts in full."""
    if preferred is None:
        return mandatory or 0.0
    if mandatory is None:
        return preferred
    return round(mandatory * SCORING["mandatory_share"] + preferred * SCORING["preferred_share"], 1)


def relevant_years(findings: list[Finding], profile: CandidateProfile) -> float:
    """Average years across the job's skills, capped so that one long career cannot dominate."""
    cap = SCORING["experience_cap_years"]
    skill_findings = [finding for finding in findings if finding.kind == "skill"]
    if not skill_findings:
        return min(profile.total_years or 0, cap)
    return round(sum(min(finding.years or 0, cap) for finding in skill_findings) / len(skill_findings), 1)


def _explain(findings: list[Finding], outcome: str) -> str:
    must = [finding for finding in findings if finding.importance == "mandatory"]
    nice = [finding for finding in findings if finding.importance == "preferred"]
    must_met = sum(finding.status == "MET" for finding in must)
    summary = f"Meets {must_met} of {len(must)} must-haves"
    if nice:
        summary += f" and {sum(finding.status == 'MET' for finding in nice)} of {len(nice)} nice-to-haves"
    summary += "."

    if outcome == "NOT_SHORTLISTED":
        missing = [finding.requirement for finding in must if finding.status == "NOT_MET"]
        summary += " Missing evidence for: " + "; ".join(missing) + "."
    elif outcome == "NEEDS_REVIEW":
        unclear = [finding.requirement for finding in must if finding.status == "REVIEW"]
        summary += " Please check: " + "; ".join(unclear) + "."
    return summary


def score_candidate(result: CandidateResult) -> CandidateResult:
    """Fill in the decision and the scores from the findings."""
    findings = result.findings
    outcome = decide_outcome(findings)
    mandatory = coverage(findings, "mandatory")
    preferred = coverage(findings, "preferred")
    return result.model_copy(update={
        "outcome": outcome,
        "mandatory_coverage": mandatory,
        "preferred_coverage": preferred,
        "match_score": match_score(mandatory, preferred),
        "relevant_years": relevant_years(findings, result.profile),
        "reason": _explain(findings, outcome),
    })


def rank_candidates(results: list[CandidateResult]) -> list[CandidateResult]:
    """Give shortlisted candidates a rank. The order of the input files has no effect."""
    def sort_key(result: CandidateResult):
        return -(result.match_score or 0), -result.relevant_years, result.display_name.casefold()

    shortlisted = sorted((r for r in results if r.outcome == "SHORTLISTED"), key=sort_key)
    others = sorted((r for r in results if r.outcome != "SHORTLISTED"), key=sort_key)

    ranked, previous, rank = [], None, 0
    for position, result in enumerate(shortlisted, 1):
        score = (result.match_score, result.relevant_years)
        if score != previous:
            rank = position  # tied candidates keep the same rank
        ranked.append(result.model_copy(update={"rank": rank}))
        previous = score
    return ranked + others
