def generate_explanation(question, context, example, bt, co):
    return f"""
    Source: Retrieved from syllabus/textbook
    Pattern: Based on previous question
    Bloom Level: {bt}
    CO: {co}
    Reason: Matches conceptual application and exam pattern
    """