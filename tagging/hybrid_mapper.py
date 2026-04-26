import ollama
import os
from dotenv import load_dotenv

load_dotenv()


def validate_question(question, bt, co):
    model_name = os.getenv("OLLAMA_MODEL", "mistral")
    
    prompt = f"""
You are an academic evaluator.

Question:
{question}

Target Bloom's Taxonomy Level: {bt}
Target Course Outcome (CO): {co}

Tasks:
1. Check if the question matches the given Bloom's level.
2. Check if it aligns with the given CO.
3. Provide a short justification.

Respond STRICTLY in this format:

Bloom Level Match: Yes/No
CO Match: Yes/No
Reason:
"""

    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt
        )

        if response and 'response' in response:
            return response['response'].strip()

        return "Validation Error: Empty response"

    except Exception as e:
        return f"Validation Error: {str(e)}"