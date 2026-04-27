"""
CLI entry point — thin wrapper over app.engine.
For the full UI, run:  streamlit run streamlit_app.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine import (
    get_available_subjects,
    get_available_units,
    get_available_pyq_years,
    is_subject_indexed,
    setup_subject,
    run_generation,
    BT_LEVELS,
    CO_OPTIONS,
)


def _pick(prompt, options, allow_all=True):
    print(f"\n{prompt}")
    for i, o in enumerate(options, 1):
        print(f"  {i}. {o}")
    raw = input("  Enter numbers (comma-separated), 'all', or 'random': ").strip().lower()
    if raw == "all" or raw == "":
        return options, "all"
    if raw == "random":
        return options, "random"
    try:
        idxs = [int(x.strip()) - 1 for x in raw.split(",")]
        chosen = [options[i] for i in idxs if 0 <= i < len(options)]
        return chosen if chosen else (options, "all")
    except Exception:
        return options, "all"


def main():
    print("\n" + "=" * 60)
    print("  EXAM QUESTION ENGINE — CLI")
    print("=" * 60)

    subjects = get_available_subjects()
    if not subjects:
        print("No subjects found. Add course materials to ./data/raw/<Subject>/")
        return

    print("\nAvailable subjects:")
    for i, s in enumerate(subjects, 1):
        indexed = "indexed" if is_subject_indexed(s) else "NOT indexed"
        print(f"  {i}. {s} [{indexed}]")

    choice = int(input("\nSelect subject number: ").strip()) - 1
    subject = subjects[choice]

    if not is_subject_indexed(subject):
        print(f"\nBuilding index for {subject}...")
        setup_subject(subject, progress_callback=lambda p, m: print(f"  [{int(p*100)}%] {m}"))

    units = get_available_units(subject)
    years = get_available_pyq_years(subject)

    selected_units, _ = _pick("Select units:", units)
    selected_bt, bt_mode = _pick("Select Bloom levels:", BT_LEVELS)
    selected_co, co_mode = _pick("Select Course Outcomes:", CO_OPTIONS)

    while True:
        try:
            num_q = int(input("\nHow many questions to generate? (1-50): "))
            if 1 <= num_q <= 50:
                break
        except ValueError:
            pass

    pyq_year = None
    if years:
        print(f"\nAvailable PYQ years: {', '.join(years)} (or press Enter to use all)")
        y = input("  Year: ").strip()
        pyq_year = y if y in years else None

    print(f"\nGenerating {num_q} questions for {subject}...\n")

    for result in run_generation(
        subject=subject,
        selected_units=selected_units,
        selected_bt=selected_bt,
        selected_co=selected_co,
        num_questions=num_q,
        pyq_year=pyq_year,
    ):
        print(f"\nQ{result['number']}. [{result['bloom_level']}] [{result['course_outcome']}] [{result['marks']}M] — {result['unit']}")
        print("-" * 60)
        print(result["question"])
        print("Validation:", "PASSED" if result["passed"] else "UNCERTAIN")
        print("Saved to bank with ID:", result["id"])

    print(f"\n{'='*60}")
    print(f"Done. All questions saved to question bank.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
