"""Step 4: show who was shortlisted, and why."""
import streamlit as st

from database import db
from models.schemas import CandidateResult
from services.export import csv_bytes
from ui.components import OUTCOME_LABELS, render_facts, render_findings, result_facts, safe_heading, years_text
from ui.state import start_over


def _table_rows(results: list[CandidateResult]) -> list[dict]:
    return [{
        "Rank": result.rank,
        "Name": result.display_name,
        "Match": result.match_score,
        "Experience": years_text(result.profile.total_years, result.profile.total_years_source) or "Not found",
        "Email": result.profile.email,
        "Phone": "; ".join(result.profile.phones),
        "Location": result.profile.location,
        "Type": result.profile.candidate_type,
    } for result in results]


def _candidate_table(results: list[CandidateResult], show_rank: bool) -> None:
    columns = ["Rank"] if show_rank else []
    columns += ["Name", "Match", "Experience", "Email", "Phone", "Location"]
    st.dataframe(_table_rows(results), hide_index=True, column_order=columns, column_config={
        "Rank": st.column_config.NumberColumn(width="small"),
        "Match": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
    })


def _add_to_shortlist(result: CandidateResult) -> None:
    """A person decided this candidate should go through."""
    batch = st.session_state.batch
    db.save_candidate(batch["job_id"], result, decided_by="Reviewer")
    batch["added_by_reviewer"].add(result.source_hash)


def _candidate_details(results: list[CandidateResult], key: str) -> None:
    """Let the user open one candidate and see the evidence for each requirement."""
    names = [f"{result.display_name}  ({result.source_name})" for result in results]
    choice = st.selectbox("See details for", names, key=f"details_{key}")
    result = results[names.index(choice)]

    with st.container(border=True):
        safe_heading(result.display_name)
        st.text(result.reason)
        if result.profile.summary:
            st.text(result.profile.summary)
        for warning in result.warnings:
            st.warning(warning)
        render_facts(result_facts(result))
        st.markdown("**Requirement checks**")
        render_findings(result.findings)

        if result.outcome == "NEEDS_REVIEW":
            if result.source_hash in st.session_state.batch["added_by_reviewer"]:
                st.success("Added to the shortlist and saved to the database.")
            else:
                st.caption("If you have read the CV and are satisfied, you can add this candidate yourself.")
                st.button("Add to shortlist", key=f"add_{result.source_hash[:12]}", on_click=_add_to_shortlist, args=(result,))


def _outcome_tab(results: list[CandidateResult], outcome: str) -> None:
    if not results:
        st.write("No candidates in this group.")
        return
    if outcome == "FILE_ERROR":
        for result in results:
            st.error(f"{result.source_name}: {result.reason}")
        st.caption("A file problem says nothing about the candidate. Fix the file and analyze it again.")
        return
    _candidate_table(results, show_rank=outcome == "SHORTLISTED")
    _candidate_details(results, outcome)


def render() -> None:
    batch = st.session_state.batch
    results: list[CandidateResult] = batch["results"]
    groups = {outcome: [r for r in results if r.outcome == outcome] for outcome in OUTCOME_LABELS}

    st.subheader("Step 4: Results")

    total, shortlisted, review, not_shortlisted = st.columns(4)
    total.metric("CVs analyzed", len(results))
    shortlisted.metric("Shortlisted", len(groups["SHORTLISTED"]))
    review.metric("Needs review", len(groups["NEEDS_REVIEW"]))
    not_shortlisted.metric("Not shortlisted", len(groups["NOT_SHORTLISTED"]))

    if batch["saved"]:
        st.success(f"{batch['saved']} shortlisted candidate(s) saved to the database.")
    else:
        st.info("Nobody met all the must-have requirements, so nothing was saved. The gates were not relaxed to fill the shortlist.")

    tabs = st.tabs([f"{OUTCOME_LABELS[outcome]} ({len(group)})" for outcome, group in groups.items()])
    for tab, (outcome, group) in zip(tabs, groups.items()):
        with tab:
            _outcome_tab(group, outcome)

    st.caption("The match score shows how much of the job the CV documents. It is not a hiring probability. "
               "CVs are self-reported, so verify details before making a decision.")

    download, new = st.columns(2)
    if groups["SHORTLISTED"]:
        download.download_button("Download shortlist (CSV)", csv_bytes(_table_rows(groups["SHORTLISTED"])),
                                 file_name="shortlist.csv", mime="text/csv", key="download_results")
    new.button("Start a new analysis", key="start_over", type="primary", on_click=start_over)
