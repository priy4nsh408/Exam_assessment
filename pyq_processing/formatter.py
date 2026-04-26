def format_pyqs(questions):
    formatted = []

    for q in questions:
        formatted.append({
            "question": q,
            "bt": "Understand",   # placeholder
            "co": "CO1",          # placeholder
            "unit": "Unit 1"      # placeholder
        })

    return formatted