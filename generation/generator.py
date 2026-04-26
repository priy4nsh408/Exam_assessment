import os
import time
import ollama
from dotenv import load_dotenv

load_dotenv()


def generate_question(context, example, bt, co):
    example_question = example.get("question", "No example provided")

    model_name = os.getenv("OLLAMA_MODEL", "mistral")

    prompt = f"""
You are an expert engineering question paper setter.

Your task is to generate a HIGH-QUALITY, ORIGINAL exam question.

CONTEXT:
{context}

REFERENCE QUESTION (DO NOT COPY):
{example_question}

REQUIREMENTS:
- Bloom Level: {bt}
- CO: {co}

Return ONLY the question.
"""

    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt
        )

        if response and 'response' in response:
            return response['response'].strip()

        return "Generation Error: Empty response"

    except Exception as e:
        return f"Generation Error: {str(e)}"