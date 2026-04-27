import os
import sys
import random
import time

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import (
    init_db,
    get_questions,
    get_question_stats,
    update_question_status,
    update_question,
    delete_question,
)
from app.engine import (
    get_available_subjects,
    get_available_units,
    get_available_pyq_years,
    is_subject_indexed,
    setup_subject,
    run_generation,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BT_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
CO_OPTIONS = ["CO1", "CO2", "CO3", "CO4", "CO5"]
MARKS_OPTIONS = [2, 5, 10]
STATUS_COLORS = {"draft": "🟡", "approved": "🟢", "rejected": "🔴"}
BT_COLORS = {
    "Remember": "#e3f2fd",
    "Understand": "#e8f5e9",
    "Apply": "#fff8e1",
    "Analyze": "#fce4ec",
    "Evaluate": "#f3e5f5",
    "Create": "#e0f7fa",
}


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Exam Question Engine",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_db()
    _inject_css()

    st.sidebar.markdown("## 📝 Exam Question Engine")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigation",
        ["Subject Setup", "Generate Questions", "Question Bank"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    _sidebar_stats()

    if page == "Subject Setup":
        page_setup()
    elif page == "Generate Questions":
        page_generate()
    elif page == "Question Bank":
        page_bank()


# ---------------------------------------------------------------------------
# Page 1 — Subject Setup
# ---------------------------------------------------------------------------

def page_setup():
    st.title("Subject Setup")
    st.caption("Manage subjects, upload course materials, and build the vector index.")

    subjects = get_available_subjects()

    # ── Upload new subject material ─────────────────────────────────────────
    with st.expander("Upload New Course Material", expanded=not subjects):
        col1, col2 = st.columns([2, 1])
        with col1:
            new_subject = st.text_input(
                "Subject Name",
                placeholder="e.g. Fluid Mechanics",
                key="new_subject_name",
            )
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Upload course material (PDF / DOCX / PPTX)",
            accept_multiple_files=True,
            type=["pdf", "docx", "pptx"],
            key="material_uploader",
        )

        if st.button("Save & Index", type="primary", disabled=not (new_subject and uploaded_files)):
            subject_dir = f"./data/raw/{new_subject.strip()}"
            os.makedirs(subject_dir, exist_ok=True)
            for f in uploaded_files:
                with open(os.path.join(subject_dir, f.name), "wb") as out:
                    out.write(f.read())
            st.success(f"Saved {len(uploaded_files)} files for **{new_subject}**.")

            bar = st.progress(0.0, text="Indexing...")

            def _cb(p, msg):
                bar.progress(p, text=msg)

            try:
                setup_subject(new_subject.strip(), _cb)
                st.success("Subject indexed and ready to use!")
                st.rerun()
            except Exception as e:
                st.error(f"Indexing failed: {e}")

    # ── Upload PYQs ─────────────────────────────────────────────────────────
    with st.expander("Upload Previous Year Questions (PYQs)"):
        all_subjects = get_available_subjects()
        if not all_subjects:
            st.info("Add a subject first.")
        else:
            pyq_subject = st.selectbox("Subject", all_subjects, key="pyq_subject_sel")
            pyq_year = st.text_input("Year", placeholder="e.g. 2023", key="pyq_year_input")
            pyq_files = st.file_uploader(
                "Upload PYQ files (PDF / DOCX)",
                accept_multiple_files=True,
                type=["pdf", "docx"],
                key="pyq_uploader",
            )
            if st.button("Save PYQs", disabled=not (pyq_subject and pyq_year and pyq_files)):
                pyq_dir = f"./data/pyqs/{pyq_subject}/{pyq_year.strip()}"
                os.makedirs(pyq_dir, exist_ok=True)
                for f in pyq_files:
                    with open(os.path.join(pyq_dir, f.name), "wb") as out:
                        out.write(f.read())
                st.success(f"Saved {len(pyq_files)} PYQ files for **{pyq_subject} {pyq_year}**.")

    # ── Subject status cards ─────────────────────────────────────────────────
    st.markdown("### Indexed Subjects")
    if not subjects:
        st.info("No subjects found. Upload course material above to get started.")
        return

    for subject in subjects:
        indexed = is_subject_indexed(subject)
        units = get_available_units(subject)
        years = get_available_pyq_years(subject)

        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                badge = "🟢 Indexed" if indexed else "🔴 Not indexed"
                st.markdown(f"**{subject}** &nbsp; {badge}")
                st.caption(f"{len(units)} units · PYQs: {', '.join(years) if years else 'none'}")
            with col2:
                if units:
                    st.caption("Units: " + ", ".join(units))
            with col3:
                if not indexed:
                    if st.button("Build Index", key=f"build_{subject}"):
                        bar = st.progress(0.0, text="Starting...")

                        def _cb(p, msg, _bar=bar):
                            _bar.progress(p, text=msg)

                        try:
                            setup_subject(subject, _cb)
                            st.success(f"{subject} indexed!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            with col4:
                if indexed:
                    if st.button("Re-index", key=f"reindex_{subject}"):
                        bar = st.progress(0.0, text="Re-indexing...")

                        def _cb(p, msg, _bar=bar):
                            _bar.progress(p, text=msg)

                        try:
                            setup_subject(subject, _cb)
                            st.success(f"{subject} re-indexed!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            st.markdown("---")


# ---------------------------------------------------------------------------
# Page 2 — Generate Questions
# ---------------------------------------------------------------------------

def page_generate():
    st.title("Generate Questions")
    st.caption("Configure your requirements and generate exam-ready questions powered by AI.")

    subjects = get_available_subjects()
    if not subjects:
        st.warning("No subjects found. Go to **Subject Setup** first.")
        return

    # ── Left panel: configuration ────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Generation Settings")

        subject = st.selectbox("Subject", subjects)

        if not is_subject_indexed(subject):
            st.warning("Subject not indexed.")
            if st.button("Index Now"):
                with st.spinner("Building index..."):
                    setup_subject(subject)
                st.success("Done!")
                st.rerun()
            return

        units = get_available_units(subject)
        selected_units = st.multiselect("Units", units, default=units)

        st.markdown("**Bloom's Taxonomy Levels**")
        selected_bt = st.multiselect("BT Levels", BT_LEVELS, default=["Understand", "Apply"])

        st.markdown("**Course Outcomes**")
        selected_co = st.multiselect("COs", CO_OPTIONS, default=CO_OPTIONS)

        st.markdown("**Marks per Question**")
        marks_mode = st.radio(
            "Marks",
            ["Auto (by BT level)", "2 marks", "5 marks", "10 marks"],
            label_visibility="collapsed",
        )

        num_questions = st.slider("Number of Questions", 1, 20, 5)

        years = get_available_pyq_years(subject)
        pyq_year = None
        if years:
            year_choice = st.selectbox("Reference PYQ Year", ["All years"] + years)
            pyq_year = None if year_choice == "All years" else year_choice

        generate_btn = st.button("Generate Questions", type="primary", use_container_width=True)

    # ── Right panel: results ──────────────────────────────────────────────────
    st.markdown(f"### Generating for: **{subject}**")

    if not selected_bt:
        st.info("Select at least one Bloom level from the sidebar.")
        return
    if not selected_co:
        st.info("Select at least one Course Outcome from the sidebar.")
        return

    if generate_btn:
        marks_override = None
        if marks_mode != "Auto (by BT level)":
            marks_override = int(marks_mode.split()[0])

        progress_bar = st.progress(0.0, text="Starting generation...")
        status_placeholder = st.empty()
        results_area = st.container()

        generated = []

        try:
            for result in run_generation(
                subject=subject,
                selected_units=selected_units if selected_units else units,
                selected_bt=selected_bt,
                selected_co=selected_co,
                num_questions=num_questions,
                marks_override=marks_override,
                pyq_year=pyq_year,
            ):
                generated.append(result)
                n = result["number"]
                total = num_questions
                progress_bar.progress(n / total, text=f"Generated {n}/{total} questions...")

                with results_area:
                    _render_question_card(result, show_actions=False)

        except Exception as e:
            st.error(f"Generation error: {e}")
            return

        progress_bar.progress(1.0, text="Done!")
        status_placeholder.success(
            f"Generated **{len(generated)} questions** and saved to the Question Bank."
        )
        st.session_state["last_generated"] = generated

    elif "last_generated" in st.session_state:
        st.info("Showing results from last generation. Run again to generate new questions.")
        for r in st.session_state["last_generated"]:
            _render_question_card(r, show_actions=False)


# ---------------------------------------------------------------------------
# Page 3 — Question Bank
# ---------------------------------------------------------------------------

def page_bank():
    st.title("Question Bank")
    st.caption("Browse, filter, approve, edit, and manage all generated questions.")

    subjects = get_available_subjects()

    # ── Filters ──────────────────────────────────────────────────────────────
    with st.expander("Filters", expanded=True):
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            f_subject = st.selectbox("Subject", ["All"] + subjects, key="f_subject")
        with col2:
            f_unit = st.selectbox("Unit", ["All"] + [f"Unit {i}" for i in range(1, 6)], key="f_unit")
        with col3:
            f_bt = st.selectbox("Bloom Level", ["All"] + BT_LEVELS, key="f_bt")
        with col4:
            f_co = st.selectbox("Course Outcome", ["All"] + CO_OPTIONS, key="f_co")
        with col5:
            f_marks = st.selectbox("Marks", ["All", "2", "5", "10"], key="f_marks")
        with col6:
            f_status = st.selectbox("Status", ["All", "draft", "approved", "rejected"], key="f_status")

    questions = get_questions(
        subject=None if f_subject == "All" else f_subject,
        unit=None if f_unit == "All" else f_unit,
        bloom_level=None if f_bt == "All" else f_bt,
        course_outcome=None if f_co == "All" else f_co,
        marks=None if f_marks == "All" else int(f_marks),
        status=None if f_status == "All" else f_status,
    )

    # ── Stats bar ─────────────────────────────────────────────────────────────
    stats_subject = None if f_subject == "All" else f_subject
    stats = get_question_stats(stats_subject)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Questions", stats["total"])
    c2.metric("Approved", stats["approved"])
    c3.metric("Draft", stats["draft"])
    c4.metric("Rejected", stats["rejected"])

    st.markdown("---")

    if not questions:
        st.info("No questions match the current filters.")
        return

    st.markdown(f"**{len(questions)} questions found**")

    # ── Bulk actions ──────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns([2, 2, 6])
    with col_a:
        if st.button("Approve All Visible"):
            for q in questions:
                update_question_status(q["id"], "approved")
            st.rerun()
    with col_b:
        if st.button("Reject All Visible"):
            for q in questions:
                update_question_status(q["id"], "rejected")
            st.rerun()

    st.markdown("---")

    # ── Question cards ────────────────────────────────────────────────────────
    for q in questions:
        _render_question_card(q, show_actions=True)


# ---------------------------------------------------------------------------
# Shared UI components
# ---------------------------------------------------------------------------

def _render_question_card(q, show_actions=True):
    status_icon = STATUS_COLORS.get(q.get("status", "draft"), "🟡")
    bt = q.get("bloom_level", "")
    bg = BT_COLORS.get(bt, "#f9f9f9")

    header = (
        f"{status_icon} &nbsp; "
        f"**Q{q['number'] if 'number' in q else q['id']}** &nbsp;|&nbsp; "
        f"`{bt}` &nbsp;|&nbsp; "
        f"`{q.get('course_outcome', '')}` &nbsp;|&nbsp; "
        f"`{q.get('unit', '')}` &nbsp;|&nbsp; "
        f"**{q.get('marks', '?')} marks**"
    )

    with st.expander(header, expanded=False):
        st.markdown(
            f"<div style='background:{bg}; padding:12px; border-radius:8px; font-size:1.05em;'>"
            f"{q.get('question', '')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        if q.get("validation"):
            with st.expander("Validation Details"):
                st.code(q["validation"], language=None)

        if show_actions and q.get("id"):
            st.markdown("")
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 3])

            with c1:
                if st.button("Approve", key=f"approve_{q['id']}", type="primary"):
                    update_question_status(q["id"], "approved")
                    st.rerun()
            with c2:
                if st.button("Reject", key=f"reject_{q['id']}"):
                    update_question_status(q["id"], "rejected")
                    st.rerun()
            with c3:
                if st.button("Delete", key=f"delete_{q['id']}"):
                    delete_question(q["id"])
                    st.rerun()
            with c4:
                new_marks = st.selectbox(
                    "Marks",
                    MARKS_OPTIONS,
                    index=MARKS_OPTIONS.index(q.get("marks", 2)) if q.get("marks") in MARKS_OPTIONS else 0,
                    key=f"marks_{q['id']}",
                    label_visibility="collapsed",
                )
                if new_marks != q.get("marks"):
                    update_question(q["id"], marks=new_marks)
                    st.rerun()
            with c5:
                new_status = st.selectbox(
                    "Status",
                    ["draft", "approved", "rejected"],
                    index=["draft", "approved", "rejected"].index(q.get("status", "draft")),
                    key=f"status_{q['id']}",
                    label_visibility="collapsed",
                )
                if new_status != q.get("status"):
                    update_question_status(q["id"], new_status)
                    st.rerun()


# ---------------------------------------------------------------------------
# Sidebar stats
# ---------------------------------------------------------------------------

def _sidebar_stats():
    try:
        stats = get_question_stats()
        st.sidebar.markdown("**Question Bank**")
        st.sidebar.markdown(
            f"- Total: **{stats['total']}**\n"
            f"- Approved: **{stats['approved']}**\n"
            f"- Draft: **{stats['draft']}**\n"
            f"- Rejected: **{stats['rejected']}**"
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _inject_css():
    st.markdown(
        """
        <style>
        .stExpander > summary { font-size: 0.95em; }
        .stButton > button { border-radius: 6px; }
        div[data-testid="metric-container"] {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
