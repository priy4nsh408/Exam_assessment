
import difflib
import os
import random
import time

# 🔹 Core pipeline imports
from ingestion.pipeline import load_documents
from ingestion.metadata_extractor import enrich_metadata
from chunking.chunker import chunk_docs
from vector_store.chroma_client import create_vector_db
from vector_store.retriever import retrieve_context

# 🔹 Generation + Validation
from generation.generator import generate_question
from tagging.hybrid_mapper import validate_question

# 🔹 PYQ Processing
from pyq_processing.parser import load_pyqs, extract_questions, load_single_pyq_file


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


# =========================================================
# SUBJECT SELECTION
# =========================================================
def select_subject():
    raw_base = "./data/raw"

    subjects = [
        folder for folder in os.listdir(raw_base)
        if os.path.isdir(os.path.join(raw_base, folder))
    ]

    if not subjects:
        print("❌ No subjects found in data/raw")
        return None

    print("\n📚 AVAILABLE SUBJECTS:\n")

    for i, subject in enumerate(subjects, 1):
        print(f"{i}. {subject}")

    while True:
        try:
            choice = int(input("\nSelect Subject Number: "))

            if 1 <= choice <= len(subjects):
                return subjects[choice - 1]

        except:
            pass

        print("⚠️ Invalid Selection")


# =========================================================
# PYQ SET SELECTION
# =========================================================
def select_pyq_set(pyq_base):
    # First check if there are subdirectories (year-based organization)
    available_sets = [
        folder for folder in os.listdir(pyq_base)
        if os.path.isdir(os.path.join(pyq_base, folder))
    ]

    if available_sets:
        # Year-based organization (like BDT/2021, BDT/2022)
        print("\n📅 AVAILABLE PYQ SETS:\n")

        for i, year in enumerate(available_sets, 1):
            print(f"{i}. {year}")

        while True:
            try:
                choice = int(input("\nSelect PYQ Set: "))

                if 1 <= choice <= len(available_sets):
                    return available_sets[choice - 1]

            except:
                pass

            print("⚠️ Invalid Selection")
    else:
        # Files directly in folder (like Propulsion/*.pdf)
        available_files = [
            file for file in os.listdir(pyq_base)
            if os.path.isfile(os.path.join(pyq_base, file)) and file.lower().endswith('.pdf')
        ]

        if not available_files:
            print("❌ No PYQ folders found")
            return None

        print("\n📄 AVAILABLE PYQ FILES:\n")

        for i, file in enumerate(available_files, 1):
            print(f"{i}. {file}")

        while True:
            try:
                choice = int(input("\nSelect PYQ File: "))

                if 1 <= choice <= len(available_files):
                    return available_files[choice - 1]

            except:
                pass

            print("⚠️ Invalid Selection")


# =========================================================
# TEACHER PREFERENCES
# =========================================================
def get_teacher_preferences():
    print("\n" + "=" * 60)
    print("📋 QUESTION GENERATION - TEACHER PREFERENCES")
    print("=" * 60)

    available_bt = [
        "Remember",
        "Understand",
        "Apply",
        "Analyze",
        "Evaluate",
        "Create"
    ]

    available_co = [
        "CO1",
        "CO2",
        "CO3",
        "CO4",
        "CO5"
    ]

    print("\n✨ Available Bloom Levels:")

    for i, bt in enumerate(available_bt, 1):
        print(f"{i}. {bt}")

    print("\n✨ Available Course Outcomes:")

    for i, co in enumerate(available_co, 1):
        print(f"{i}. {co}")

    # Number of questions
    while True:
        try:
            num_q = int(input("\n📌 Number of Questions (1-50): "))

            if 1 <= num_q <= 50:
                break

        except:
            pass

        print("⚠️ Invalid Input")

    # Bloom selection
    bt_input = input(
        "\n📝 Enter Bloom Levels (1,2 or all/random): "
    ).strip().lower()

    if bt_input == "all":
        selected_bt = available_bt

    elif bt_input == "random":
        selected_bt = available_bt

    else:
        try:
            indices = [
                int(x.strip()) - 1
                for x in bt_input.split(",")
            ]

            selected_bt = [
                available_bt[i]
                for i in indices
                if 0 <= i < len(available_bt)
            ]

        except:
            selected_bt = available_bt

    # CO selection
    co_input = input(
        "\n📝 Enter COs (1,2 or all/random): "
    ).strip().lower()

    if co_input == "all":
        selected_co = available_co

    elif co_input == "random":
        selected_co = available_co

    else:
        try:
            indices = [
                int(x.strip()) - 1
                for x in co_input.split(",")
            ]

            selected_co = [
                available_co[i]
                for i in indices
                if 0 <= i < len(available_co)
            ]

        except:
            selected_co = available_co

    return (
        num_q,
        selected_bt,
        selected_co,
        bt_input,
        co_input
    )


# =========================================================
# MAIN
# =========================================================
def main():

    print("\n" + "=" * 70)
    print("🤖 AI QUESTION GENERATION & ASSESSMENT SYSTEM")
    print("=" * 70)

    # =====================================================
    # 1. SUBJECT SELECTION
    # =====================================================
    subject = select_subject()

    if not subject:
        return

    print(f"\n✅ Selected Subject: {subject}")

    raw_path = f"./data/raw/{subject}"
    pyq_folder = resolve_subject_folder("./data/pyqs", subject)

    if not pyq_folder:
        available = [
            folder for folder in os.listdir("./data/pyqs")
            if os.path.isdir(os.path.join("./data/pyqs", folder))
        ]
        print(
            "❌ No matching PYQ subject folder found for",
            subject
        )
        print("   Available PYQ subjects:", ", ".join(available))
        return

    pyq_base = pyq_folder
    db_path = f"./data/db/chroma/{subject}"

    print(f"🔗 Resolved PYQ folder: {pyq_base}")

    # =====================================================
    # 2. LOAD DOCUMENTS
    # =====================================================
    docs = load_documents(raw_path)

    if not docs:
        print("❌ No documents loaded")
        return

    print(f"✅ Loaded {len(docs)} documents")

    # =====================================================
    # 3. ADD METADATA
    # =====================================================
    docs = enrich_metadata(docs)

    for doc in docs:
        doc.metadata["subject"] = subject

    # =====================================================
    # 4. CHUNK DOCUMENTS
    # =====================================================
    chunks = chunk_docs(docs)

    if not chunks:
        print("❌ Chunking failed")
        return

    print(f"✅ Created {len(chunks)} chunks")

    # =====================================================
    # 5. CREATE / LOAD VECTOR DB
    # =====================================================
    if os.path.exists(db_path):

        vectordb = create_vector_db(
            None,
            persist_directory=db_path
        )

        print("✅ Loaded existing Vector DB")

    else:

        vectordb = create_vector_db(
            chunks,
            persist_directory=db_path
        )

        print("✅ Created new Vector DB")

    # =====================================================
    # 6. QUERY INPUT
    # =====================================================
    query = input("\n🔍 Enter Topic / Query: ")

    # =====================================================
    # 7. RETRIEVE CONTEXT
    # =====================================================
    context = ""

    try:

        context_docs = retrieve_context(
            vectordb,
            query
        )

        if not context_docs:

            print("⚠️ Retrieval failed")
            context = "Explain concept clearly."

        else:

            if isinstance(context_docs, str):

                context = context_docs

            else:

                context = "\n".join([
                    doc.page_content
                    for doc in context_docs
                    if hasattr(doc, "page_content")
                ])

    except Exception as e:

        print(f"⚠️ Retrieval Error: {e}")

        context = "Explain concept clearly."

    # Reduce token usage
    context = context[:2000]

    print("\n🔍 CONTEXT PREVIEW:\n")
    print(context[:500])

    # =====================================================
    # 8. LOAD PYQS
    # =====================================================
    selected_set = select_pyq_set(pyq_base)

    if not selected_set:
        return

    pyq_path = os.path.join(
        pyq_base,
        selected_set
    )

    print(f"\n📂 Loading PYQs from: {selected_set}")

    # Check if selected_set is a file or directory
    if os.path.isfile(pyq_path):
        # Single file selected (like Propulsion/*.pdf)
        pyq_docs = load_single_pyq_file(pyq_path, selected_set)
    else:
        # Directory selected (like BDT/2021/)
        pyq_docs = load_pyqs(pyq_path)

    questions = extract_questions(pyq_docs)

    print(f"📘 Extracted {len(questions)} PYQs")

    # =====================================================
    # 9. LOAD QUESTION BANK
    # =====================================================
    question_bank_questions = []

    qb_path = None

    for folder in os.listdir(pyq_base):
        candidate_path = os.path.join(pyq_base, folder)

        if not os.path.isdir(candidate_path):
            continue

        normalized_name = folder.strip().lower().replace("_", " ")

        if normalized_name == "question bank":
            qb_path = candidate_path
            break

    if qb_path and os.path.exists(qb_path):

        print("\n📚 Loading Question Bank...")

        qb_docs = load_pyqs(qb_path)

        qb_questions = extract_questions(qb_docs)

        question_bank_questions = [
            {
                "question": q,
                "source": "question_bank"
            }
            for q in qb_questions
        ]

        print(
            f"✅ Loaded {len(question_bank_questions)} "
            f"Question Bank Questions"
        )

    # =====================================================
    # 10. CREATE PYQ STRUCTURE
    # =====================================================
    pyqs = []

    for q in questions:

        pyqs.append({
            "question": q,
            "bt": "Understand",
            "co": "CO1",
            "unit": "Unit 1",
            "source": "pyq"
        })

    pyqs.extend(question_bank_questions)

    if not pyqs:
        print("❌ No PYQs found")
        return

    # =====================================================
    # 11. SELECT EXAMPLE
    # =====================================================
    example = random.choice(pyqs)

    print("\n📘 REFERENCE QUESTION:\n")
    print(example["question"])

    # =====================================================
    # 12. TEACHER PREFERENCES
    # =====================================================
    (
        num_questions,
        selected_bt,
        selected_co,
        bt_mode,
        co_mode
    ) = get_teacher_preferences()

    # =====================================================
    # 13. GENERATE QUESTIONS
    # =====================================================
    generated_questions = []

    for q_num in range(num_questions):

        print("\n" + "=" * 60)
        print(
            f"🔁 GENERATING QUESTION "
            f"{q_num + 1}/{num_questions}"
        )
        print("=" * 60)

        # BT selection
        if bt_mode == "random":
            bt = random.choice(selected_bt)
        else:
            bt = selected_bt[
                q_num % len(selected_bt)
            ]

        # CO selection
        if co_mode == "random":
            co = random.choice(selected_co)
        else:
            co = selected_co[
                q_num % len(selected_co)
            ]

        print(f"📋 BT: {bt} | CO: {co}")

        # =================================================
        # GENERATION
        # =================================================
        question = generate_question(
            context,
            example,
            bt,
            co
        )

        print("\n🧠 GENERATED QUESTION:\n")
        print(question)

        # =================================================
        # VALIDATION
        # =================================================
        validation = validate_question(
            question,
            bt,
            co
        )

        print("\n✅ VALIDATION:\n")
        print(validation)

        # =================================================
        # STORE
        # =================================================
        generated_questions.append({
            "number": q_num + 1,
            "question": question,
            "bt": bt,
            "co": co,
            "validation": validation
        })

        time.sleep(1)

    # =====================================================
    # FINAL OUTPUT
    # =====================================================
    print("\n" + "=" * 70)
    print("🎯 FINAL GENERATED QUESTIONS")
    print("=" * 70)

    for q in generated_questions:

        print(f"\nQ{q['number']}")
        print("-" * 60)

        print(f"\n📌 Bloom Level: {q['bt']}")
        print(f"📌 Course Outcome: {q['co']}")

        print(f"\n📝 QUESTION:\n")
        print(q["question"])

        print(f"\n✅ VALIDATION:\n")
        print(q["validation"])

        print("\n" + "=" * 70)


# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    main()
