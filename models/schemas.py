"""The data shapes used across the app.

Every service passes these objects around, so this file is the best place to
start reading. The groups below follow the order of the analysis:
requirements -> candidate profile -> findings -> final result.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Allowed values ---
Importance = Literal["mandatory", "preferred", "ignore"]
RequirementKind = Literal["skill", "experience", "education", "other", "personal"]
DegreeLevel = Literal["", "diploma", "bachelor", "master", "phd"]
Status = Literal["MET", "NOT_MET", "REVIEW"]
Outcome = Literal["SHORTLISTED", "NEEDS_REVIEW", "NOT_SHORTLISTED", "FILE_ERROR"]


# --- 1. What the job asks for ---
class Requirement(BaseModel):
    """One line of the job description, in a form the code can check."""
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    text: str = Field(min_length=1, max_length=4000)  # the job's original wording
    importance: Importance = "mandatory"
    kind: RequirementKind = "other"
    skills: str = ""  # comma-separated skill names
    operator: Literal["ALL", "ANY"] = "ALL"  # ALL = every skill, ANY = one is enough
    min_years: float | None = Field(default=None, ge=0, le=60)
    degree: DegreeLevel = ""
    degree_field: str = ""

    @field_validator("text")
    @classmethod
    def text_is_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Requirement text cannot be blank.")
        return value.strip()

    @field_validator("importance", "kind", "degree", mode="before")
    @classmethod
    def lower_case_choices(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("operator", mode="before")
    @classmethod
    def upper_case_operator(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @property
    def skill_list(self) -> list[str]:
        return [skill.strip() for skill in self.skills.split(",") if skill.strip()]


# --- 2. What the CV says ---
class DegreeInfo(BaseModel):
    level: DegreeLevel
    text: str
    in_progress: bool = False


class CandidateProfile(BaseModel):
    """Data extracted from a CV. Contact details never affect the decision."""
    name: str = ""
    email: str = ""
    phones: list[str] = []
    location: str = ""
    current_title: str = ""
    candidate_type: str = "Not clear"  # Student, Employee or Not clear
    total_years: float | None = None
    total_years_source: str = ""  # "stated" or "job dates"
    has_experience_section: bool = False
    degrees: list[DegreeInfo] = []
    skills: list[str] = []
    summary: str = ""

    @property
    def education(self) -> str:
        return "; ".join(degree.text for degree in self.degrees)


# --- 3. How the CV compares with each requirement ---
class Finding(BaseModel):
    """The result of checking one requirement against one CV."""
    requirement_id: str
    requirement: str
    importance: Importance
    kind: RequirementKind
    status: Status
    evidence: str = ""  # exact words from the CV
    reason: str = ""  # plain explanation, always filled in
    years: float | None = None


class CandidateResult(BaseModel):
    """Everything known about one CV after analysis."""
    source_name: str
    source_hash: str = ""
    cv_text: str = ""
    profile: CandidateProfile = CandidateProfile()
    outcome: Outcome
    findings: list[Finding] = []
    mandatory_coverage: float | None = None
    preferred_coverage: float | None = None
    match_score: float | None = None
    relevant_years: float = 0
    rank: int | None = None
    reason: str = ""
    warnings: list[str] = []

    @property
    def display_name(self) -> str:
        return self.profile.name or self.source_name


# --- 4. What the AI must return (checked before anything is trusted) ---
class RequirementExtraction(BaseModel):
    requirements: list[Requirement]


class AiFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    requirement_id: str
    answer: Literal["found", "not_found", "unclear"] = "unclear"
    quote: str = ""

    @field_validator("answer", mode="before")
    @classmethod
    def lower_case_answer(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class CvExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    current_title: str = ""
    summary: str = ""
    education: list[str] = []
    skills: list[str] = []
    findings: list[AiFinding] = []
