import os
import sys
import difflib
import random
import streamlit as st

# Ensure root directory is on sys.path when running from the app folder
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from ingestion.pipeline import load_documents
from ingestion.metadata_extractor import enrich_metadata
from chunking.chunker import chunk_docs
from vector_store.chroma_client import create_vector_db
from vector_store.retriever import retrieve_context
from pyq_processing.parser import load_pyqs, extract_questions, load_single_pyq_file
from generation.generator import generate_question, generate_questions
from tagging.hybrid_mapper import validate_question, validate_questions


def normalize_folder_name(name):
    return "".join(
        ch for ch in name.lower()
        if ch.isalnum()
    )


def resolve_subject_folder(base_path, subject):
    if not os.path.isdir(base_path):
        return None

    normalized_target = normalize_folder_name(subject)
    candidates = [
        folder for folder in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, folder))
    ]

    for folder in candidates:
        if normalize_folder_name(folder) == normalized_target:
            return os.path.join(base_path, folder)

    closest = difflib.get_close_matches(
        subject,
        candidates,
        n=1,
        cutoff=0.6
    )

    if closest:
        return os.path.join(base_path, closest[0])

    return None


def list_subjects(raw_base):
    if not os.path.isdir(raw_base):
        return []

    return sorted(
        folder for folder in os.listdir(raw_base)
        if os.path.isdir(os.path.join(raw_base, folder))
    )


def get_unit_options(chunks):
    units = sorted({
        chunk.metadata.get("unit", "Unknown")
        for chunk in chunks
        if chunk.metadata.get("unit", "Unknown") != "Unknown"
    })
    return units


def build_pyq_options(pyq_folder):
    if not pyq_folder or not os.path.isdir(pyq_folder):
        return []

    files = [
        file for file in os.listdir(pyq_folder)
        if os.path.isfile(os.path.join(pyq_folder, file)) and file.lower().endswith((".pdf", ".docx"))
    ]
    dirs = [
        folder for folder in os.listdir(pyq_folder)
        if os.path.isdir(os.path.join(pyq_folder, folder))
    ]
    return sorted(dirs + files)


def load_pyq_collection(pyq_base, selected_set):
    path = os.path.join(pyq_base, selected_set)
    if os.path.isfile(path):
        return load_single_pyq_file(path, selected_set)
    return load_pyqs(path)


def get_cached_docs_and_chunks(raw_path):
    cache_key = os.path.abspath(raw_path)

    if (
        "cached_raw_path" not in st.session_state
        or st.session_state["cached_raw_path"] != cache_key
    ):
        docs = load_documents(raw_path)
        docs = enrich_metadata(docs)
        chunks = chunk_docs(docs)

        st.session_state["cached_raw_path"] = cache_key
        st.session_state["cached_docs"] = docs
        st.session_state["cached_chunks"] = chunks

    return st.session_state["cached_docs"], st.session_state["cached_chunks"]


def get_cached_vector_db(db_path, chunks):
    if "vectordbs" not in st.session_state:
        st.session_state["vectordbs"] = {}

    cache_key = os.path.abspath(db_path)

    if cache_key in st.session_state["vectordbs"]:
        return st.session_state["vectordbs"][cache_key], True

    if os.path.exists(db_path) and os.listdir(db_path):
        vectordb = create_vector_db(None, persist_directory=db_path)
        loaded_existing = True
    else:
        vectordb = create_vector_db(chunks, persist_directory=db_path)
        loaded_existing = False

    st.session_state["vectordbs"][cache_key] = vectordb
    return vectordb, loaded_existing


def main():
    st.set_page_config(
        page_title="AI Exam Generator",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("AI Exam System — Streamlit Frontend")
    st.markdown(
        "Use this app to prepare subjects, load PYQs, generate original questions, and validate them with your existing AI pipeline."
    )

    # Initialize session state for generated questions
    if "generated_questions" not in st.session_state:
        st.session_state["generated_questions"] = []

    # Sidebar for all parameters
    with st.sidebar:
        st.header("Configuration")

        raw_base = os.path.join(ROOT_DIR, "data", "raw")
        subjects = list_subjects(raw_base)

        if not subjects:
            st.error("No subjects found in `data/raw`. Add documents and try again.")
            return

        subject = st.selectbox("Subject", subjects, key="subject")

        if not subject:
            return

        pyq_folder = resolve_subject_folder(os.path.join(ROOT_DIR, "data", "pyqs"), subject)
        if not pyq_folder:
            st.warning("No matching PYQ folder found for this subject. Check `data/pyqs` naming.")

        raw_path = os.path.join(ROOT_DIR, "data", "raw", subject)
        db_path = os.path.join(ROOT_DIR, "data", "db", "chroma", subject)

        with st.spinner("Loading documents and metadata..."):
            docs, chunks = get_cached_docs_and_chunks(raw_path)

        units = get_unit_options(chunks)
        if not units:
            st.warning("No unit metadata detected in documents. The pipeline can still run, but unit filtering will be unavailable.")
            units = ["All"]

        selected_unit = st.selectbox("Unit", units, key="unit")
        semantic_query = st.text_input("Optional semantic topic or query", value="", key="semantic_query")

        pyq_options = build_pyq_options(pyq_folder) if pyq_folder else []
        selected_set = None
        if pyq_options:
            selected_set = st.selectbox("PYQ set / file", pyq_options, key="pyq_set")
        else:
            st.warning("No PYQ sets found for the selected subject.")

        st.markdown("---")
        st.subheader("Teacher preferences")

        num_questions = st.slider("Number of questions", min_value=1, max_value=20, value=5, key="num_questions")

        bt_choices = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
        bt_selected = st.multiselect("Bloom levels", bt_choices, default=["Understand", "Apply"], key="bt_selected")
        bt_mode = st.radio("Bloom selection mode", ["Sequential", "Random"], index=0, key="bt_mode")

        co_choices = ["CO1", "CO2", "CO3", "CO4", "CO5"]
        co_selected = st.multiselect("Course outcomes", co_choices, default=["CO1", "CO2"], key="co_selected")
        co_mode = st.radio("CO selection mode", ["Sequential", "Random"], index=0, key="co_mode")

        if not bt_selected or not co_selected:
            st.warning("Select at least one Bloom level and one CO to enable question generation.")

        generate_button = st.button("Generate Questions", type="primary")

    if not docs:
        st.error("No documents were loaded. Check that the selected subject folder contains supported files (.pdf, .docx, .pptx).")
        return

    st.success(f"Loaded {len(docs)} documents.")

    if not chunks:
        st.error("Chunking failed. Verify the source documents and try again.")
        return

    st.info(f"Created {len(chunks)} semantic chunks.")

    # Main content area
    if generate_button:
        if not pyq_folder or not selected_set:
            st.error("Select a PYQ set or file before generating questions.")
            return

        if not bt_selected or not co_selected:
            st.error("At least one Bloom level and one CO must be selected.")
            return

        with st.spinner("Loading/creating vector database..."):
            vectordb, loaded_existing = get_cached_vector_db(db_path, chunks)
            if loaded_existing:
                st.success("Loaded existing vector database.")
            else:
                st.success("Created new vector database.")

        with st.spinner("Retrieving context..."):
            if selected_unit == "All":
                unit_filter = None
            else:
                unit_filter = selected_unit

            context = retrieve_context(
                vectordb,
                query=semantic_query or "Explain the selected topic clearly.",
                unit=unit_filter,
                subject=subject
            )

        if not context:
            context = "Explain concept clearly."
            st.warning("No relevant context found. The generator will use a fallback prompt.")

        context = context[:2000]
        pyq_path = os.path.join(pyq_folder, selected_set)
        with st.spinner("Loading PYQ reference questions..."):
            pyq_docs = load_pyq_collection(pyq_folder, selected_set)
            example_questions = extract_questions(pyq_docs)

        if not example_questions:
            st.warning("No questions extracted from the selected PYQ set. The generator will still run, but results may be less precise.")

        example_question_text = example_questions[0] if example_questions else "No example question available."
        example = {
            "question": example_question_text
        }

        st.markdown("#### Reference question")
        st.write(example["question"])

        # Build question specs for batch generation
        bt_sequence = []
        co_sequence = []

        for idx in range(num_questions):
            if bt_mode == "Random":
                bt = random.choice(bt_selected)
            else:
                bt = bt_selected[idx % len(bt_selected)]

            if co_mode == "Random":
                co = random.choice(co_selected)
            else:
                co = co_selected[idx % len(co_selected)]

            bt_sequence.append(bt)
            co_sequence.append(co)

        with st.spinner("Generating questions..."):
            questions = generate_questions(context, example, bt_sequence, co_sequence)

        with st.spinner("Validating questions..."):
            validations = validate_questions(questions, bt_sequence, co_sequence)

        generated = []
        for idx, (bt, co, question, validation) in enumerate(zip(bt_sequence, co_sequence, questions, validations), start=1):
            generated.append({
                "index": idx,
                "bt": bt,
                "co": co,
                "question": question,
                "validation": validation
            })

        st.session_state["generated_questions"] = generated
        st.success("Question generation complete.")

    # Display generated questions with dropdowns
    if st.session_state["generated_questions"]:
        st.header(f"Generated Questions ({len(st.session_state['generated_questions'])})")

        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("Clear All Questions", type="secondary"):
                st.session_state["generated_questions"] = []
                st.rerun()

        # Create a copy to avoid modifying while iterating
        questions_to_show = st.session_state["generated_questions"].copy()

        for i, item in enumerate(questions_to_show):
            with st.expander(f"Question {item['index']}: {item['bt']} | {item['co']}", expanded=False):
                col1, col2 = st.columns([4, 1])

                with col1:
                    st.write("**Generated Question:**")
                    st.write(item["question"])

                with col2:
                    if st.button("Delete", key=f"delete_{i}"):
                        # Remove the question from session state
                        st.session_state["generated_questions"].pop(i)
                        st.rerun()

                st.write("**Validation:**")
                st.code(item["validation"], language="text")

    st.markdown("---")
    st.caption("Streamlit frontend for AI Exam System. Make sure OLLAMA_MODEL is configured in your .env file.")


if __name__ == "__main__":
    main()
