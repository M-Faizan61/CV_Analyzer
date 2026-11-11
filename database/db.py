"""The SQLite database: one file on this computer, no server to install.

There are two tables:
  jobs                    the job descriptions that were analyzed
  shortlisted_candidates  the people shortlisted for each job

A record can be created by an analysis or by a person, and a person can read, update
and delete it. Re-running an analysis updates a candidate's record instead of adding
a copy, and never overwrites what a person has changed. All values are passed as
query parameters, never joined into the SQL text.
"""
import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from config.settings import database_path
from models.schemas import CandidateResult, Requirement
from services.shortlister import RULES_VERSION

STATUSES = ("New", "Contacted", "Interview", "Hired", "Rejected")
CANDIDATE_TYPES = ("Student", "Employee", "Not clear")

# The details a person can correct. Once corrected, an analysis leaves them alone.
_DETAIL_COLUMNS = ("name", "email", "phone", "location", "current_title", "candidate_type", "total_years", "education", "skills")
_EDITABLE_COLUMNS = _DETAIL_COLUMNS + ("status", "notes")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_MAX_YEARS = 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    requirements_json TEXT NOT NULL,
    fingerprint       TEXT NOT NULL UNIQUE,
    analysis_method   TEXT NOT NULL,
    model             TEXT NOT NULL DEFAULT '',
    rules_version     TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shortlisted_candidates (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id             INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_key      TEXT NOT NULL,
    name               TEXT NOT NULL,
    email              TEXT NOT NULL DEFAULT '',
    phone              TEXT NOT NULL DEFAULT '',
    location           TEXT NOT NULL DEFAULT '',
    current_title      TEXT NOT NULL DEFAULT '',
    candidate_type     TEXT NOT NULL DEFAULT '',
    total_years        REAL,
    education          TEXT NOT NULL DEFAULT '',
    skills             TEXT NOT NULL DEFAULT '',
    match_score        REAL,
    rank               INTEGER,
    reason             TEXT NOT NULL DEFAULT '',
    findings_json      TEXT NOT NULL DEFAULT '[]',
    cv_text            TEXT NOT NULL DEFAULT '',
    source_file        TEXT NOT NULL DEFAULT '',
    decided_by         TEXT NOT NULL DEFAULT 'System',
    status             TEXT NOT NULL DEFAULT 'New',
    notes              TEXT NOT NULL DEFAULT '',
    edited_by_person   INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    UNIQUE (job_id, candidate_key)
);

CREATE INDEX IF NOT EXISTS idx_candidates_job ON shortlisted_candidates (job_id);
"""

# Built from the constant column names above, never from user input.
_KEEP_PERSON_EDITS = ",\n    ".join(
    f"{column} = CASE WHEN edited_by_person = 1 THEN {column} ELSE excluded.{column} END" for column in _DETAIL_COLUMNS)

_SAVE_CANDIDATE = f"""
INSERT INTO shortlisted_candidates (
    job_id, candidate_key, name, email, phone, location, current_title, candidate_type, total_years,
    education, skills, match_score, rank, reason, findings_json, cv_text, source_file, decided_by,
    created_at, updated_at)
VALUES (
    :job_id, :candidate_key, :name, :email, :phone, :location, :current_title, :candidate_type, :total_years,
    :education, :skills, :match_score, :rank, :reason, :findings_json, :cv_text, :source_file, :decided_by,
    :now, :now)
ON CONFLICT (job_id, candidate_key) DO UPDATE SET
    {_KEEP_PERSON_EDITS},
    match_score = excluded.match_score, rank = excluded.rank, reason = excluded.reason,
    findings_json = excluded.findings_json, cv_text = excluded.cv_text, source_file = excluded.source_file,
    decided_by = excluded.decided_by, updated_at = excluded.updated_at
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open the database, commit on success, roll back on error, always close."""
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    """Create the tables if they do not exist yet. Safe to call every time the app starts."""
    with _connect() as connection:
        connection.executescript(_SCHEMA)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(shortlisted_candidates)")}
        if "edited_by_person" not in columns:  # a database made by an earlier version of the app
            connection.execute("ALTER TABLE shortlisted_candidates ADD COLUMN edited_by_person INTEGER NOT NULL DEFAULT 0")


# --- Jobs ---
def save_job(title: str, description: str, requirements: list[Requirement], method: str, model: str = "") -> int:
    """Save a job and return its id. The same job with the same requirements is reused."""
    title = title.strip() or "Untitled job"
    requirements_json = json.dumps([item.model_dump() for item in requirements], ensure_ascii=False)
    fingerprint = hashlib.sha256(f"{title}\n{description}\n{requirements_json}".encode("utf-8")).hexdigest()

    with _connect() as connection:
        connection.execute(
            """INSERT INTO jobs (title, description, requirements_json, fingerprint, analysis_method, model, rules_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (fingerprint) DO UPDATE SET analysis_method = excluded.analysis_method, model = excluded.model""",
            (title, description, requirements_json, fingerprint, method, model, RULES_VERSION, _now()))
        row = connection.execute("SELECT id FROM jobs WHERE fingerprint = ?", (fingerprint,)).fetchone()
    return row["id"]


def list_jobs() -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT jobs.id, jobs.title, jobs.analysis_method, jobs.created_at, COUNT(c.id) AS candidates
               FROM jobs LEFT JOIN shortlisted_candidates AS c ON c.job_id = jobs.id
               GROUP BY jobs.id ORDER BY jobs.id DESC""").fetchall()
    return [dict(row) for row in rows]


def delete_job(job_id: int) -> None:
    """Remove a job and all of its candidate records."""
    with _connect() as connection:
        connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


# --- Candidates: checking what a person typed ---
def check_details(details: dict) -> dict:
    """Clean the details of a record. Raises ValueError with a message for the screen."""
    cleaned = {name: value.strip() if isinstance(value, str) else value for name, value in details.items()}
    if not cleaned["name"]:
        raise ValueError("Please enter a name.")
    if cleaned["email"] and not _EMAIL.fullmatch(cleaned["email"]):
        raise ValueError("That email address does not look right.")
    if cleaned["candidate_type"] not in CANDIDATE_TYPES:
        raise ValueError(f"Unknown candidate type: {cleaned['candidate_type']}")
    if cleaned["status"] not in STATUSES:
        raise ValueError(f"Unknown status: {cleaned['status']}")
    years = cleaned["total_years"]
    if years is not None and not 0 <= years <= _MAX_YEARS:
        raise ValueError(f"Experience must be between 0 and {_MAX_YEARS} years.")
    return cleaned


def _person_key(email: str, phone: str, name: str, fallback: str = "") -> str:
    """Identify a person within a job, so the same person twice is one record."""
    phone_digits = "".join(char for char in phone if char.isdigit())
    return email.lower() or phone_digits or name.lower() or fallback


# --- Candidates: create ---
def save_candidate(job_id: int, result: CandidateResult, decided_by: str = "System") -> None:
    """Save an analysis result: a new record, or an update if the person is already saved."""
    profile = result.profile
    with _connect() as connection:
        connection.execute(_SAVE_CANDIDATE, {
            "job_id": job_id,
            "candidate_key": _person_key(profile.email, profile.phones[0] if profile.phones else "", profile.name, result.source_hash),
            "name": result.display_name,
            "email": profile.email,
            "phone": "; ".join(profile.phones),
            "location": profile.location,
            "current_title": profile.current_title,
            "candidate_type": profile.candidate_type,
            "total_years": profile.total_years,
            "education": profile.education,
            "skills": ", ".join(profile.skills),
            "match_score": result.match_score,
            "rank": result.rank,
            "reason": result.reason,
            "findings_json": json.dumps([finding.model_dump() for finding in result.findings], ensure_ascii=False),
            "cv_text": result.cv_text,
            "source_file": result.source_name,
            "decided_by": decided_by,
            "now": _now(),
        })


def create_candidate(job_id: int, **details) -> int:
    """Add a record typed in by a person, without any analysis. Returns its id."""
    defaults = {"name": "", "email": "", "phone": "", "location": "", "current_title": "", "candidate_type": "Not clear",
                "total_years": None, "education": "", "skills": "", "status": "New", "notes": ""}
    values = check_details(defaults | details)
    columns = ", ".join(_EDITABLE_COLUMNS)
    placeholders = ", ".join(f":{column}" for column in _EDITABLE_COLUMNS)
    query = f"""INSERT INTO shortlisted_candidates
                    (job_id, candidate_key, {columns}, decided_by, edited_by_person, created_at, updated_at)
                VALUES (:job_id, :candidate_key, {placeholders}, 'Manual entry', 1, :now, :now)"""
    values.update(job_id=job_id, candidate_key=_person_key(values["email"], values["phone"], values["name"]), now=_now())
    try:
        with _connect() as connection:
            return connection.execute(query, values).lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("This candidate is already saved for this job.") from None


# --- Candidates: read ---
def list_candidates(search: str = "", job_id: int | None = None, status: str = "", candidate_type: str = "") -> list[dict]:
    """Return saved candidates, best match first, with optional filters."""
    query = """SELECT c.*, jobs.title AS job_title FROM shortlisted_candidates AS c
               JOIN jobs ON jobs.id = c.job_id WHERE 1 = 1"""
    values: list = []
    if search.strip():
        like = f"%{search.strip()}%"
        query += " AND (c.name LIKE ? OR c.email LIKE ? OR c.phone LIKE ? OR c.location LIKE ? OR c.skills LIKE ?)"
        values += [like] * 5
    if job_id is not None:
        query += " AND c.job_id = ?"
        values.append(job_id)
    if status:
        query += " AND c.status = ?"
        values.append(status)
    if candidate_type:
        query += " AND c.candidate_type = ?"
        values.append(candidate_type)
    query += " ORDER BY c.job_id DESC, c.rank IS NULL, c.rank, c.match_score DESC, c.name"

    with _connect() as connection:
        rows = connection.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def get_candidate(candidate_id: int) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            """SELECT c.*, jobs.title AS job_title FROM shortlisted_candidates AS c
               JOIN jobs ON jobs.id = c.job_id WHERE c.id = ?""", (candidate_id,)).fetchone()
    return dict(row) if row else None


# --- Candidates: update ---
def update_candidate(candidate_id: int, **changes) -> None:
    """Change any editable field of a record. Fields not passed in stay as they are."""
    current = get_candidate(candidate_id)
    if current is None:
        raise ValueError("This record no longer exists.")

    values = check_details({column: changes.get(column, current[column]) for column in _EDITABLE_COLUMNS})
    corrected = any(values[column] != current[column] for column in _DETAIL_COLUMNS)
    assignments = ", ".join(f"{column} = :{column}" for column in _EDITABLE_COLUMNS)
    values.update(id=candidate_id, now=_now(), edited=int(corrected or current["edited_by_person"]))
    with _connect() as connection:
        connection.execute(
            f"UPDATE shortlisted_candidates SET {assignments}, edited_by_person = :edited, updated_at = :now WHERE id = :id", values)


# --- Candidates: delete ---
def delete_candidate(candidate_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM shortlisted_candidates WHERE id = ?", (candidate_id,))
