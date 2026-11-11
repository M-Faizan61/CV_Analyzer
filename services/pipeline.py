"""The full analysis, step by step. Start here to follow what the system does.

    Step 1  read_requirements   job description -> requirements
    Step 2  analyze_cv          one CV -> text -> profile -> findings -> decision
    Step 3  analyze_batch       every CV -> ranked results
    Step 4  save_shortlist      shortlisted candidates -> database
"""
import hashlib
import re
from collections.abc import Callable

from pydantic import BaseModel, Field

from database import db
from models.schemas import AiFinding, CandidateResult, Requirement
from services.cv_parser import apply_ai_profile, build_profile, extract_with_ai
from services.document_reader import read_document
from services.job_parser import parse_job_locally, parse_job_with_ai
from services.openrouter_client import OpenRouterError
from services.requirement_checker import check_requirement
from services.shortlister import rank_candidates, score_candidate

# Text aimed at an AI instead of a recruiter is a warning sign in a CV.
_ADDRESSED_TO_AI = re.compile(r"ignore (?:all |any )?(?:previous|prior|above) instructions|you are (?:an? )?(?:ai|assistant|chatgpt|language model)"
                              r"|(?:shortlist|select|hire) this candidate", re.I)


class AiOptions(BaseModel):
    """Present only when the AI method is used. The key stays in memory only."""
    api_key: str = Field(default="", repr=False)
    model: str = ""


class CvInput(BaseModel):
    """One CV waiting for analysis: a file (content) or typed text (text)."""
    name: str
    source: str  # Upload, Manual entry or Folder
    content: bytes = b""
    text: str = ""
    known_name: str = ""  # the name typed into the manual form

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.content or self.text.encode("utf-8")).hexdigest()


def active_requirements(requirements: list[Requirement]) -> list[Requirement]:
    """Requirements that take part in decisions. Personal conditions never do."""
    return [item for item in requirements if item.importance != "ignore" and item.kind != "personal"]


def read_requirements(job_text: str, ai: AiOptions | None = None) -> list[Requirement]:
    """Step 1: turn the job description into requirements."""
    if ai:
        return parse_job_with_ai(job_text, ai.api_key, ai.model)
    return parse_job_locally(job_text)


def _file_problem(cv: CvInput, message: str) -> CandidateResult:
    """A file problem is not a judgement about the candidate."""
    return CandidateResult(source_name=cv.name, source_hash=cv.fingerprint, outcome="FILE_ERROR", reason=message)


def analyze_cv(cv: CvInput, requirements: list[Requirement], ai: AiOptions | None = None) -> CandidateResult:
    """Step 2: analyze one CV against the requirements."""
    # 2a. Read the text
    try:
        cv_text = cv.text or read_document(cv.name, cv.content)
    except ValueError as error:
        return _file_problem(cv, str(error))
    if len(cv_text.strip()) < 20:
        return _file_problem(cv, "This CV has too little text to analyze.")

    # 2b. Extract the candidate's details
    profile, warnings = build_profile(cv_text)
    if cv.known_name:
        profile.name = cv.known_name
    if _ADDRESSED_TO_AI.search(cv_text):
        warnings.append("This CV contains text aimed at an AI system. Please read it carefully.")

    # 2c. In the AI method, let the model look for evidence
    checks = active_requirements(requirements)
    ai_findings: dict[str, AiFinding] = {}
    if ai:
        try:
            extraction = extract_with_ai(cv_text, checks, ai.api_key, ai.model)
        except OpenRouterError as error:
            if error.fatal:
                raise
            warnings.append(f"The AI could not read this CV, so the manual rules were used. ({error})")
        else:
            profile = apply_ai_profile(profile, extraction, cv_text)
            ai_findings = {finding.requirement_id: finding for finding in extraction.findings}

    # 2d. Check every requirement, then decide
    findings = [check_requirement(item, profile, cv_text, ai_findings.get(item.id)) for item in checks]
    result = CandidateResult(source_name=cv.name, source_hash=cv.fingerprint, cv_text=cv_text,
                             profile=profile, outcome="NEEDS_REVIEW", findings=findings, warnings=warnings)
    return score_candidate(result)


def analyze_batch(cvs: list[CvInput], requirements: list[Requirement], ai: AiOptions | None = None,
                  on_progress: Callable[[int, int, str], None] | None = None) -> list[CandidateResult]:
    """Step 3: analyze every CV on its own, then rank them together."""
    results = []
    for number, cv in enumerate(cvs, 1):
        if on_progress:
            on_progress(number, len(cvs), cv.name)
        results.append(analyze_cv(cv, requirements, ai))
    return rank_candidates(results)


def save_shortlist(title: str, description: str, requirements: list[Requirement], results: list[CandidateResult],
                   ai: AiOptions | None = None) -> tuple[int, int]:
    """Step 4: save the job and its shortlisted candidates. Returns (job id, number saved)."""
    job_id = db.save_job(title, description, requirements, "AI" if ai else "Manual", ai.model if ai else "")
    shortlisted = [result for result in results if result.outcome == "SHORTLISTED"]
    for result in shortlisted:
        db.save_candidate(job_id, result, decided_by="System")
    return job_id, len(shortlisted)


def new_cvs_only(existing: list[CvInput], incoming: list[CvInput]) -> tuple[list[CvInput], int]:
    """Drop exact duplicate CVs. Returns the new ones and how many were skipped."""
    seen = {cv.fingerprint for cv in existing}
    added = []
    for cv in incoming:
        if cv.fingerprint not in seen:
            seen.add(cv.fingerprint)
            added.append(cv)
    return added, len(incoming) - len(added)
