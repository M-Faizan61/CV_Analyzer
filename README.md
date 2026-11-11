# CV Analyzer

Reads CVs, extracts each candidate's details, compares them with a job description,
shortlists the people who meet it, and saves the shortlist in a local database.

For the commands to run and test it, see **[SIMPLE_GUIDE.md](SIMPLE_GUIDE.md)**.

## Quick start

Double-click `start.bat`, then open http://127.0.0.1:8520

## How to use it

| Step | What you do |
|---|---|
| 1. Method | Choose **Manual** (no API key) or **AI with OpenRouter** (your API key) |
| 2. Job description | Paste or upload it, then check the requirements the system found |
| 3. CVs | **Upload files**, **Enter manually**, or **Use CV folder** |
| 4. Results | See who is shortlisted and why. They are saved to the database automatically |

The **Shortlisted candidates** page is a full CRUD screen: add records by hand, search and filter
them, edit any detail, delete a record or a whole job, and download a CSV.

## How candidates are decided

| Result | Meaning |
|---|---|
| **Shortlisted** | Every must-have requirement has evidence in the CV |
| **Needs review** | Nothing is missing, but a must-have needs a person to read the CV |
| **Not shortlisted** | A must-have has no evidence in the CV |
| **File problem** | The file could not be read. This says nothing about the candidate |

Shortlisted candidates are ranked by match score, then by relevant years of experience.
Equal candidates share a rank. Each result shows the requirement, the decision, the reason
and the exact words from the CV.

The match score is 70% must-haves and 30% nice-to-haves (`config/scoring.json`). It measures
how much of the job the CV documents. It is not a hiring probability.

**Manual and AI use the same decision rules.** The AI only finds information. Python checks
every AI quote against the CV and makes every decision, so the AI cannot put someone on the
shortlist by itself, and it can never overrule the skill rules (for example, GitHub does not
prove Git). If the AI fails on one CV, the manual rules are used for it and a warning is shown.

Personal conditions such as age, gender or domicile are never used. They are listed
separately for a person to handle under your hiring policy.

## Project structure

```text
app.py                     Starts the app: page setup and navigation only
start.bat                  Double-click to run

config/
  settings.py              Paths, limits and OpenRouter options
  skill_taxonomy.json      Skills, aliases and which skills prove which
  scoring.json             Score weights and the experience cap
models/
  schemas.py               The data shapes. Start reading here
prompts/                   Instructions sent to the AI
services/                  The analysis. Start with pipeline.py
  pipeline.py              The whole process, step by step
  document_reader.py       PDF, DOCX or TXT -> text
  cv_sections.py           Finds the sections of a CV
  contact_extractor.py     Name, email, phone, location, job title
  experience_extractor.py  Years of experience
  education_extractor.py   Degrees
  cv_parser.py             Combines the extractors into one profile
  job_parser.py            Job description -> requirements
  skill_matcher.py         Does the CV prove this skill?
  requirement_checker.py   Checks one requirement against one CV
  shortlister.py           Decision, score and ranking
  openrouter_client.py     The only file that calls the API
  manual_cv.py             Turns the manual form into CV text
  export.py                CSV downloads
database/
  db.py                    The SQLite database
ui/                        The screens
  analyze_page.py          Shows the steps
  step_method.py           Step 1
  step_job.py              Step 2
  step_cvs.py              Step 3
  step_results.py          Step 4
  database_page.py         Shortlisted candidates page
  components.py            Shared display pieces
  state.py                 What the app remembers between clicks
  theme.py                 Styling
tests/                     Automatic tests
data/
  cvs/                     Put CV files here for the folder option
  job_descriptions/        28 test job descriptions (see docs/test_jobs.md)
  cv_analyzer.db           The database, created on first run
```

## The database

SQLite, stored in `data/cv_analyzer.db`. There is no server to install.

| Table | Holds |
|---|---|
| `jobs` | Title, description, reviewed requirements, method and model |
| `shortlisted_candidates` | Contact details, experience, education, skills, match, rank, evidence, CV text, status and notes |

Records come from three places: shortlisted candidates, people you approve from Needs review,
and people you add by hand. The **Added by** column shows which.

| Action | Where | In `database/db.py` |
|---|---|---|
| Create | **Add a record** tab, or an analysis | `create_candidate`, `save_candidate` |
| Read | **Records** tab | `list_candidates`, `get_candidate` |
| Update | **Edit** tab on a record | `update_candidate` |
| Delete | **Delete** tab on a record, or **Delete this job** | `delete_candidate`, `delete_job` |

Running the same analysis again updates a record instead of creating a copy, and keeps your
status, notes and corrections. Match and rank can only be set by the analysis.

## Privacy

- The app only listens on this computer (127.0.0.1).
- The Manual method sends nothing anywhere.
- The AI method sends job and CV text to OpenRouter and the model you choose, after you agree.
  Free models may keep what you send.
- A key typed into the app stays in memory until you close the tab. A key in `.env` stays on this computer.
- The database holds personal data in an ordinary unencrypted file. Delete it when no longer needed.
- `.gitignore` excludes `.env`, CVs and the database. This project is not a git repository and nothing is uploaded.

## Known limits

- Scanned PDFs cannot be read, because there is no OCR. They show as a File problem.
- The Manual method understands the skills in `config/skill_taxonomy.json`, and other names only when
  they are spelled the same in the job and the CV. Add aliases there to teach it more.
- The Manual method cannot judge soft skills or free-text requirements, so these start as Nice to have.
  The AI method can check them.
- Years for a skill come from statements such as `Python: 5 years`, otherwise they are estimated from
  job dates. The reason text says which was used.
- CVs are self-reported. The system shows what a CV claims, not whether it is true.
- There are no user accounts, so use it on your own computer only.

See `cv_analyzer_requirements.md` for the rules, and `docs/roadmap.md` for what could come next.
