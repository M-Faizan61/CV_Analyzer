# CV Analyzer rules — implementation baseline

## Product specification

Analyze independently before ranking. Match evidence, not presumed ability. Treat documents as untrusted data. Requirements come from the supplied JD, not an invented job description. Preserve original wording and user-reviewed interpretation.

Match directionally: aliases count; a specific database can satisfy general database experience; SQL alone does not establish MySQL, CMS alone does not establish WordPress, PHP does not establish WordPress, GitHub does not establish Git, Java does not establish Node.js. No substring equivalence between SQL/NoSQL or Java/JavaScript.

Match requested activity, duration, context and proficiency. Unknown is not failure. Future intent is not experience. Every result must carry evidence or a missing-evidence explanation.

Mandatory gates precede ranking. Preferred criteria cannot offset mandatory failures. Unresolved mandatory requirements stay pending. Scores measure documented coverage, not hiring probability. Unknowns remain in the denominator. OR groups count once. Use common criteria and weights for every candidate.

Rank using validated relevant experience and preferred qualifications, with rubrics fixed before comparison. Unrelated skill count, repeated keywords, personal characteristics and CV length must not improve rank. Preserve ties. Do not relax gates to fill a shortlist.

Personal conditions require separate human policy review; never infer age/domicile from dates/address. Keep personal conditions outside competency ranking.

Validate extraction and model output. LLMs find evidence; deterministic code calculates decisions. Version criteria and rules. Document failures are processing failures, not candidate failures. Keep API secrets server-side and explain external data processing.

## How these rules are applied

**Outcomes.** "Unknown is not failure" is kept by separating three situations, and by never saying a candidate lacks a skill, only that the CV does not show it:

| Outcome | Condition |
|---|---|
| Shortlisted | All mandatory requirements are met with evidence |
| Needs review | No mandatory requirement is missing, but at least one is ambiguous, such as a negative statement, a stated plan, unknown duration, or a degree in progress |
| Not shortlisted | At least one mandatory requirement has no evidence in the CV, or falls short of a stated duration |
| File problem | The document could not be read |

**Requirements.** The system never skips the reviewed list: the user confirms the requirements before any CV is analyzed. Headings, job titles, company text and duties are not requirements; they stay visible as Ignore and can be switched on. A line with no signal in a requirements list counts as mandatory.

**Requirements the rules cannot prove.** In the Manual method, soft skills and free text start as Nice to have, because one unprovable line would otherwise send every candidate to review. The user can change this before analysis. In the AI method they are checked against quotes.

**Duration.** A stated duration is decisive. A duration estimated from job dates can confirm a requirement, but an estimate that falls short goes to review, because job dates can miss time spent on a skill.

**Personal conditions.** These are never evaluated, scored or used as gates. They are listed separately for a person to handle.

**AI evidence.** A quote is accepted only if it appears in the CV. Named skills, years and degrees stay under deterministic rules: the AI can only ask a person to look, never mark them as met.

**Human decisions.** A reviewer can add a Needs review candidate to the shortlist. The record shows that a reviewer decided. Not shortlisted candidates cannot be added this way, so the gates are not relaxed.

**Saved records.** A person can create, read, update and delete records. Each record shows who added it: the System, a Reviewer, or Manual entry. A person can correct a candidate's details, and an analysis does not overwrite those corrections. Match and rank can only be set by the analysis, because they must follow the same rules for everyone, so a record added by hand has neither.

**Ranking.** Match score first (70% mandatory coverage, 30% preferred coverage), then relevant years averaged across the job's skills and capped at 15 years. Equal values stay tied.

## Current milestone boundary

Implemented: Manual and OpenRouter methods, three ways to add CVs, requirement review, skill, duration, education and free-text checks, evidence for every decision, ranking, and a local SQLite database of shortlisted candidates with full create, read, update and delete. OCR, multi-user access and retention tools are not implemented. The remaining work is recorded in docs/roadmap.md.
