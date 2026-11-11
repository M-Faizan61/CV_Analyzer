"""Decide whether a CV shows a skill.

Matching is directional and needs real evidence (see cv_analyzer_requirements.md):
  * aliases count:                    "NodeJS" proves "node.js"
  * specific proves general:          "MySQL" proves "database"
  * general does NOT prove specific:  "CMS" does not prove "WordPress"
  * no substring matches:             "NoSQL" does not prove "SQL"
  * plans are not experience:         "Planning to learn SQL" does not prove "SQL"
"""
import re
from dataclasses import dataclass, field

from config.settings import load_json_config
from services.text_utils import contains, remove_term, split_statements

TAXONOMY = load_json_config("skill_taxonomy.json")
_ALIASES: dict[str, list[str]] = TAXONOMY["aliases"]
_CHILDREN: dict[str, list[str]] = TAXONOMY["children"]
_RELATED: dict[str, list[str]] = TAXONOMY["related"]
SOFT_SKILLS: set[str] = set(TAXONOMY["soft_skills"])

# Every alias, longest first, so "technical seo" is found before "seo".
_ALIAS_TO_SKILL = sorted(
    ((alias, skill) for skill, aliases in _ALIASES.items() for alias in aliases),
    key=lambda pair: len(pair[0]), reverse=True)

_NEGATION = re.compile(r"\b(?:no|not|without|never|lack\w*)\b", re.I)
_FUTURE_INTENT = re.compile(
    r"\b(?:plan(?:s|ning)? to|want(?:s|ing)? to|wish(?:es)? to|hop(?:e|es|ing) to|intend(?:s|ing)? to"
    r"|aspir\w+ to|interested in|studying|beginner|exposure to)\b"
    r"|(?<!machine )(?<!deep )\blearn(?:ing)?\b", re.I)
_SOMEONE_ELSE = re.compile(r"\b(?:team|company|employer|organi[sz]ation)\s+(?:use[sd]?|using|works? with|worked with)\b", re.I)
_SQL_ACTIVITY = re.compile(r"\b(?:wrote|writing|write|optimi[sz]ed|optimi[sz]ing)\b.*\bqueries\b", re.I)

_MAX_EVIDENCE_LINES = 3


@dataclass
class SkillCheck:
    status: str  # MET, NOT_MET or REVIEW
    reason: str
    evidence: list[str] = field(default_factory=list)


def canonical(value: str) -> str:
    """Turn any alias into the standard skill name: "ReactJS" -> "react"."""
    cleaned = value.strip().lower()
    for skill, aliases in _ALIASES.items():
        if cleaned == skill or cleaned in aliases:
            return skill
    return cleaned


def aliases_of(skill: str) -> list[str]:
    return _ALIASES.get(skill, [skill])


def accepted_skills(skill: str) -> list[str]:
    """The skill itself plus the more specific skills that prove it."""
    return [skill] + _CHILDREN.get(skill, [])


def children_of(skill: str) -> list[str]:
    return _CHILDREN.get(skill, [])


def mentions_skill(text: str, skill: str) -> bool:
    return any(contains(text, alias) for alias in aliases_of(skill))


def find_skills(text: str) -> list[str]:
    """List the known skills in a text, in the order they appear."""
    remaining = text
    found: dict[str, int] = {}
    for alias, skill in _ALIAS_TO_SKILL:
        if contains(remaining, alias):
            found.setdefault(skill, text.lower().find(alias.split()[0]))
            remaining = remove_term(remaining, alias)  # "technical seo" must not also count as "seo"
    return sorted(found, key=found.get)


def _proves_sql(statement: str) -> bool:
    """Writing queries for a SQL database shows SQL, even if "SQL" is not written alone."""
    return (_SQL_ACTIVITY.search(statement) is not None
            and any(mentions_skill(statement, name) for name in ("mysql", "postgresql", "sqlite", "sql server")))


def find_skill_evidence(cv_text: str, skill: str) -> SkillCheck:
    """Check one skill against the CV and explain the result."""
    skill = canonical(skill)
    accepted = accepted_skills(skill)
    positive, doubtful, negated = [], [], []

    for statement in split_statements(cv_text):
        mentioned = any(mentions_skill(statement, name) for name in accepted)
        if not mentioned and not (skill == "sql" and _proves_sql(statement)):
            continue
        if _NEGATION.search(statement):
            negated.append(statement)
        elif _FUTURE_INTENT.search(statement) or _SOMEONE_ELSE.search(statement):
            doubtful.append(statement)
        else:
            positive.append(statement)

    # "No SQL experience" beside "Skills: SQL" is a contradiction a person must settle.
    if negated:
        lines = list(dict.fromkeys(negated + positive))[:_MAX_EVIDENCE_LINES]
        return SkillCheck("REVIEW", "The CV mentions this with a negative word. Please read the line.", lines)
    if positive:
        return SkillCheck("MET", "Found in the CV.", list(dict.fromkeys(positive))[:_MAX_EVIDENCE_LINES])
    if doubtful:
        lines = list(dict.fromkeys(doubtful))[:_MAX_EVIDENCE_LINES]
        return SkillCheck("REVIEW", "Mentioned only as a plan or as something others did. Please read the line.", lines)

    related = [name for name in _RELATED.get(skill, []) if mentions_skill(cv_text, name)]
    if related:
        return SkillCheck("NOT_MET", f"Not found. The CV only shows related skills: {', '.join(related)}.")
    return SkillCheck("NOT_MET", "Not found in the CV.")
