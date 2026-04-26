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
from pyq_processing.parser import load_pyqs, extract_questions


def get_teacher_preferences():
    """Get CO and BT preferences from teacher"""
    print("\n" + "="*60)
    print("📋 QUESTION GENERATION - TEACHER PREFERENCES")
    print("="*60)
    
    # Available options
    available_bt = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
    available_co = ["CO1", "CO2", "CO3", "CO4", "CO5"]
    
    print("\n✨ Available Bloom Levels:")
    for i, bt in enumerate(available_bt, 1):
        print(f"  {i}. {bt}")
    
    print("\n✨ Available Course Outcomes:")
    for i, co in enumerate(available_co, 1):
        print(f"  {i}. {co}")
    
    # Get number of questions
    while True:
        try:
            num_q = int(input("\n📌 How many questions to generate? (1-50): "))
            if 1 <= num_q <= 50:
                break
            print("⚠️ Please enter a number between 1 and 50")
        except ValueError:
            print("⚠️ Invalid input. Please enter a number.")
    
    # Get Bloom Levels selection
    print("\n📝 Select Bloom Levels (comma-separated numbers, e.g., 1,3,5 or 'all'):")
    print("  'all' = use all levels, 'random' = random for each question")
    bt_input = input("  Your choice: ").strip().lower()
    
    if bt_input == "all":
        selected_bt = available_bt
    elif bt_input == "random":
        selected_bt = available_bt  # Will randomize in loop
    else:
        try:
            indices = [int(x.strip()) - 1 for x in bt_input.split(",")]
            selected_bt = [available_bt[i] for i in indices if 0 <= i < len(available_bt)]
            if not selected_bt:
                selected_bt = available_bt
                print("⚠️ Invalid selection. Using all Bloom Levels.")
        except:
            selected_bt = available_bt
            print("⚠️ Invalid input. Using all Bloom Levels.")
    
    # Get Course Outcomes selection
    print("\n📝 Select Course Outcomes (comma-separated numbers, e.g., 1,2,3 or 'all'):")
    print("  'all' = use all COs, 'random' = random for each question")
    co_input = input("  Your choice: ").strip().lower()
    
    if co_input == "all":
        selected_co = available_co
    elif co_input == "random":
        selected_co = available_co  # Will randomize in loop
    else:
        try:
            indices = [int(x.strip()) - 1 for x in co_input.split(",")]
            selected_co = [available_co[i] for i in indices if 0 <= i < len(available_co)]
            if not selected_co:
                selected_co = available_co
                print("⚠️ Invalid selection. Using all Course Outcomes.")
        except:
            selected_co = available_co
            print("⚠️ Invalid input. Using all Course Outcomes.")
    
    return num_q, selected_bt, selected_co, bt_input, co_input


def main():
    # -------------------------------
    # 1. Load Documents (Content)
    # -------------------------------
    docs = load_documents("./data/raw/BDT")

    if not docs:
        print("❌ No documents loaded.")
        return

    print(f"✅ Loaded {len(docs)} documents")

    # -------------------------------
    # 2. Add Metadata
    # -------------------------------
    docs = enrich_metadata(docs)

    # -------------------------------
    # 3. Chunk
    # -------------------------------
    chunks = chunk_docs(docs)

    if not chunks:
        print("❌ Chunking failed.")
        return

    print(f"✅ Created {len(chunks)} chunks")

    # -------------------------------
    # 4. Vector DB (Create / Load)
    # -------------------------------
    db_path = "./data/db/chroma"

    if os.path.exists(db_path):
        vectordb = create_vector_db(None)
        print("✅ Loaded existing Vector DB")
    else:
        vectordb = create_vector_db(chunks)
        print("✅ Created new Vector DB")

    # -------------------------------
    # 5. Retrieve Context
    # -------------------------------
    query = "beam deflection simply supported beam UDL"

    context = ""  # ✅ initialize first

    try:
       context_docs =retrieve_context(vectordb, query)

       if not context_docs:
          print("⚠️ Retrieval failed — using fallback context")
          context = "Explain the concept clearly with relevant formulas."
       else:
          # 🔁 Handle BOTH cases (string OR Document list)
          if isinstance(context_docs, str):
             context = context_docs
          else:
            context = "\n".join(
                [doc.page_content for doc in context_docs if hasattr(doc, "page_content")]
            )

    except Exception as e:
      print(f"⚠️ Retrieval error: {e}")
    context = "Explain the concept clearly with relevant formulas."

    # ✅ Now this will NEVER crash
    print("\n🔍 Retrieved Context Preview:\n")
    print(context[:500])

    # -------------------------------
# 6. Load + Extract PYQs
# -------------------------------
pyq_path = "./data/pyqs/BDT/2021"

if not os.path.exists(pyq_path):
    print(f"❌ PYQ path not found: {pyq_path}")
    pyqs = []
else:
    print("📂 PYQ Files:", os.listdir(pyq_path))

    pyq_docs = load_pyqs(pyq_path)

    print(f"📄 Loaded {len(pyq_docs)} PYQ pages")

    questions = extract_questions(pyq_docs)

    print(f"📘 Extracted {len(questions)} PYQs")

    pyqs = [
        {
            "question": q,
            "bt": "Understand",
            "co": "CO1",
            "unit": "Unit 1"
        }
        for q in questions
    ]
    # -------------------------------
    # 7. Select Example PYQ
    # -------------------------------
    example = random.choice(pyqs)

    print("\n📘 Reference PYQ:\n")
    print(example["question"])

    # -------------------------------
    # 8. Get Teacher Preferences & Generate Questions
    # -------------------------------
    num_questions, selected_bt, selected_co, bt_mode, co_mode = get_teacher_preferences()
    
    generated_questions = []
    
    for q_num in range(num_questions):
        print(f"\n{'='*60}")
        print(f"🔁 GENERATING QUESTION {q_num + 1}/{num_questions}")
        print(f"{'='*60}")
        
        # Select BT based on mode
        if bt_mode == "random":
            bt = random.choice(selected_bt)
        else:
            bt = selected_bt[q_num % len(selected_bt)]
        
        # Select CO based on mode
        if co_mode == "random":
            co = random.choice(selected_co)
        else:
            co = selected_co[q_num % len(selected_co)]
        
        print(f"📋 Bloom Level: {bt} | CO: {co}")
        
        question = None
        validation = None
        context =''
        # Attempt to generate and validate question
        for attempt in range(3):
            print(f"\n  ↻ Attempt {attempt + 1}/3")
            
            question = generate_question(context, example, bt, co)
            print(f"  Generated: {question[:100]}...")
            
            validation = validate_question(question, bt, co)
            
            if "Yes" in validation:
                print(f"  ✅ Validation Passed")
                break
            else:
                print(f"  ⚠️ Validation Failed, retrying...")
                time.sleep(2)  # Shorter delay between retries
        
        # Store the generated question
        generated_questions.append({
            "number": q_num + 1,
            "question": question,
            "bloom_level": bt,
            "course_outcome": co,
            "validation": validation
        })
        
        time.sleep(1)  # Brief delay between questions

    # -------------------------------
    # Final Output - All 10 Questions
    # -------------------------------
    print(f"\n{'='*60}")
    print(f"🎯 ALL {num_questions} GENERATED QUESTIONS")
    print(f"{'='*60}\n")
    
    for q in generated_questions:
        print(f"\nQ{q['number']}. [Bloom Level: {q['bloom_level']}, Course Outcome: {q['course_outcome']}]")
        print("-" * 60)
        print(f"\n📝 QUESTION:\n{q['question']}\n")
        print(f"✅ VALIDATION:\n{q['validation']}\n")
        print("=" * 60)


if __name__ == "__main__":
    main()