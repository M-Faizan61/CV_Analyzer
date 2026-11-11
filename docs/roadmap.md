# Implementation milestones

## Done

1. **Working local system:** step-by-step UI, Manual and OpenRouter methods, typed, uploaded and folder CVs, requirement review, directional skill matching, evidence for every decision, and CSV exports.
2. **Structured evidence:** years from statements and job dates, degree levels and subjects, Needs review with reviewer decisions, and a larger skill taxonomy.
3. **Ranking:** match score, then capped relevant years, with ties preserved.
4. **Database:** SQLite records of shortlisted candidates, with full create, read, update and delete, search and filters.
5. **Test set:** 28 job descriptions with expected results worked out by hand (`docs/test_jobs.md`).

## Next

1. **Document robustness:** OCR for scanned PDFs, and better handling of multi-column layouts.
2. **Richer requirements:** nested AND/OR logic, proficiency rubrics, and non-English CVs.
3. **Evaluation:** a labelled set of CVs to measure accuracy, especially for AI models.
4. **Deployment readiness:** user accounts, encrypted storage, and retention and deletion tools.
