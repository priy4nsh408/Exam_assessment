"""
Seed demo data for MechAssess.

Inserts three hand-crafted, fully-grounded questions (theory, numerical,
drawing) directly into the SQLite DB - each with a real source_chunk,
answer_key, and explanations - plus a matching answer_scheme (with its own
answer_id) for each. This works without Ollama or ChromaDB being populated,
so you can demo the grading pipeline immediately.

Run from the backend/ directory (with the venv active):
    python seed_demo_data.py

Or from the repo root:
    python backend/seed_demo_data.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generation.langgraph_pipeline import (
    init_db, save_question, create_answer_scheme, question_sha256,
)


def make_question(qid, text, q_type, subject, unit, bloom_level, bloom_label,
                   co, po, marks, difficulty, source_chunk, answer_key,
                   generation_explanation, answer_key_explanation):
    return {
        "id": qid, "text": text, "type": q_type, "subject": subject, "unit": unit,
        "bloom_level": bloom_level, "bloom_label": bloom_label, "co": co, "po": po,
        "marks": marks, "difficulty": difficulty,
        "answer_key": answer_key, "source_chunk": source_chunk,
        "generation_explanation": generation_explanation,
        "answer_key_explanation": answer_key_explanation,
        "sha256": question_sha256(qid),  # unique by id, not text - fine for seed data
        "created_at": datetime.now().isoformat(),
    }


THEORY_SOURCE = (
    "The first law of thermodynamics states that energy cannot be created or "
    "destroyed, only converted from one form to another - it is a statement of "
    "conservation of energy. For a closed system undergoing a process, the change "
    "in internal energy (dU) equals the heat added to the system (Q) minus the "
    "work done by the system (W): dU = Q - W. Internal energy is a property of "
    "the system's state, while heat and work are path-dependent quantities that "
    "describe energy transfer across the system boundary."
)
THEORY_ANSWER_KEY = (
    "The first law of thermodynamics is a statement of the conservation of "
    "energy: energy can be converted between forms but never created or "
    "destroyed. For a closed system, the change in internal energy equals the "
    "heat added minus the work done by the system, expressed as dU = Q - W. "
    "Internal energy depends only on the state of the system, whereas heat and "
    "work depend on the path taken between states."
)

NUMERICAL_SOURCE = (
    "A Carnot engine operating between a heat source at 800 K and a heat sink "
    "at 400 K produces 150 kW of net work output. The thermal efficiency of a "
    "Carnot engine is eta = 1 - T_L/T_H = 1 - 400/800 = 0.5 (50%). Heat supplied "
    "from the source is Q_H = W_net / eta = 150 / 0.5 = 300 kW. Heat rejected to "
    "the sink is Q_L = Q_H - W_net = 300 - 150 = 150 kW."
)
NUMERICAL_ANSWER_KEY = (
    "eta = 1 - T_L/T_H = 1 - 400/800 = 0.5 (50% efficiency). "
    "Q_H = W_net / eta = 150 / 0.5 = 300 kW (heat supplied from source). "
    "Q_L = Q_H - W_net = 300 - 150 = 150 kW (heat rejected to sink)."
)

DRAWING_TEXT = (
    "Draw a labeled block diagram of a simple Rankine cycle power plant "
    "showing the boiler, turbine, condenser and pump, with the boiler outlet "
    "pressure marked as 50mm and the connecting pipe diameter marked as 30mm "
    "on the diagram."
)
DRAWING_SOURCE = (
    "A Rankine cycle power plant consists of four main components connected in "
    "a closed loop: the boiler (heat is added to convert feedwater to "
    "high-pressure steam), the turbine (steam expands, doing work to drive a "
    "generator), the condenser (low-pressure steam is cooled back to liquid "
    "water), and the pump (liquid water is pressurized and returned to the "
    "boiler). All four components and their connecting pipework must be "
    "clearly labeled with appropriate dimensions."
)


def seed():
    init_db()

    theory_q = make_question(
        qid="Q-DEMO-THEORY",
        text="State and explain the first law of thermodynamics for a closed system.",
        q_type="theory", subject="Thermodynamics", unit="Unit 1: Laws of Thermodynamics",
        bloom_level=2, bloom_label="Understand", co="CO1", po="PO1", marks=10, difficulty="easy",
        source_chunk=THEORY_SOURCE, answer_key=THEORY_ANSWER_KEY,
        generation_explanation=(
            'This is seed/demo data for Thermodynamics -> "Unit 1: Laws of Thermodynamics", '
            "targeting Bloom's Level 2 (Understand) under CO1. Grounded in a hand-written "
            "passage about the first law (see source_chunk)."
        ),
        answer_key_explanation=(
            "The answer key restates the first law's conservation-of-energy principle and "
            "the dU = Q - W relationship directly from the source passage, without adding "
            "any fact not present in that passage."
        ),
    )

    numerical_q = make_question(
        qid="Q-DEMO-NUMERICAL",
        text=(
            "A Carnot engine operates between a source at 800 K and a sink at 400 K, "
            "producing 150 kW of net work. Find the thermal efficiency, heat supplied, "
            "and heat rejected."
        ),
        q_type="numerical", subject="Thermodynamics", unit="Unit 2: Power Cycles",
        bloom_level=3, bloom_label="Apply", co="CO2", po="PO2", marks=10, difficulty="medium",
        source_chunk=NUMERICAL_SOURCE, answer_key=NUMERICAL_ANSWER_KEY,
        generation_explanation=(
            'This is seed/demo data for Thermodynamics -> "Unit 2: Power Cycles", targeting '
            "Bloom's Level 3 (Apply) under CO2. Grounded in a hand-written worked solution "
            "(see source_chunk)."
        ),
        answer_key_explanation=(
            "The answer key is the worked solution itself: efficiency from the Carnot "
            "formula, heat supplied from work/efficiency, heat rejected by energy balance - "
            "all three values traceable to the source passage."
        ),
    )

    drawing_q = make_question(
        qid="Q-DEMO-DRAWING",
        text=DRAWING_TEXT,
        q_type="drawing", subject="Engineering Drawing", unit="Unit 2: Sections",
        bloom_level=3, bloom_label="Apply", co="CO5", po="PO1", marks=20, difficulty="medium",
        source_chunk=DRAWING_SOURCE, answer_key=DRAWING_SOURCE,
        generation_explanation=(
            'This is seed/demo data for Engineering Drawing -> "Unit 2: Sections", targeting '
            "Bloom's Level 3 (Apply) under CO5. The question text itself specifies the "
            "expected parts (boiler, turbine, condenser, pump) and dimensions (50mm, 30mm), "
            "which the grading rubric extracts automatically."
        ),
        answer_key_explanation=(
            "Reference is the source passage describing all four required components - "
            "used by the drawing evaluator to know which parts/dimensions to check for."
        ),
    )

    schemes = []
    for q in (theory_q, numerical_q, drawing_q):
        save_question(q)
        scheme = create_answer_scheme(q, question_number=1)
        schemes.append((q, scheme))

    return schemes


SAMPLE_ANSWERS = {
    "theory": {
        "good": (
            "The first law of thermodynamics is the conservation of energy: energy "
            "cannot be created or destroyed, only converted between forms. For a "
            "closed system, the change in internal energy equals the heat added to "
            "the system minus the work done by the system, expressed as dU = Q - W. "
            "Internal energy is a state property, while heat and work are path-dependent."
        ),
        "poor": "Energy is conserved I think. Heat and work are related somehow in thermodynamics.",
    },
    "numerical": {
        "good": (
            "eta = 1 - T_L/T_H = 1 - 400/800 = 0.5\n"
            "Q_H = W_net / eta = 150 / 0.5 = 300 kW\n"
            "Q_L = Q_H - W_net = 300 - 150 = 150 kW"
        ),
        "no_formula": "The efficiency is 50%, heat supplied is 300 kW, heat rejected is 150 kW.",
        "wrong_final": (
            "eta = 1 - T_L/T_H = 1 - 400/800 = 0.5\n"
            "Q_H = W_net / eta = 150 / 0.5 = 300 kW\n"
            "Q_L = Q_H - W_net = 300 - 150 = 120 kW"
        ),
    },
}


if __name__ == "__main__":
    seeded = seed()
    print("\nSeeded demo questions + answer schemes:\n")
    for q, scheme in seeded:
        print(f"  [{q['type'].upper()}]")
        print(f"    question_id : {q['id']}")
        print(f"    answer_id   : {scheme['id']}")
        print(f"    marks       : {q['marks']}")
        print()

    print("Sample student answers to paste into each grader's 'Answer ID' field:\n")

    theory_scheme = seeded[0][1]["id"]
    print(f"--- Theory Evaluator (Answer ID: {theory_scheme}) ---")
    print("GOOD answer:\n" + SAMPLE_ANSWERS["theory"]["good"])
    print("\nPOOR answer:\n" + SAMPLE_ANSWERS["theory"]["poor"])

    numerical_scheme = seeded[1][1]["id"]
    print(f"\n--- Numerical Grader (Answer ID: {numerical_scheme}) ---")
    print("GOOD solution (full marks expected):\n" + SAMPLE_ANSWERS["numerical"]["good"])
    print("\nNO-FORMULA solution (-1 mark expected):\n" + SAMPLE_ANSWERS["numerical"]["no_formula"])
    print("\nWRONG-FINAL-ANSWER solution (-1 mark expected):\n" + SAMPLE_ANSWERS["numerical"]["wrong_final"])

    drawing_scheme = seeded[2][1]["id"]
    print(f"\n--- Drawing Evaluator (Answer ID: {drawing_scheme}) ---")
    print(
        "Drawing grading needs an actual image upload (the rubric checks what's\n"
        "visually detected in the picture). Upload ANY image along with this\n"
        "Answer ID to see the rubric run - since there's no LLaVA vision model\n"
        "result for a placeholder image, it will report all parts/dimensions as\n"
        "missing (which is itself a correct demo of the deduction logic: -1 per\n"
        "missing part, -0.5 per missing dimension). To see a 'good' result you'd\n"
        "need a real drawing image whose labels/dimensions match: boiler, turbine,\n"
        "condenser, pump, 50mm, 30mm."
    )
