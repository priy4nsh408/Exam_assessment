import ollama
import os
import re
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


def _parse_validation_blocks(response):
    blocks = []
    current = []

    for line in response.splitlines():
        text = line.strip()
        if not text:
            continue

        if re.match(r'^(?:\d+[\.)]\s*|Question\s+\d+:)', text):
            if current:
                blocks.append("\n".join(current).strip())
            current = [text]
        else:
            current.append(text)

    if current:
        blocks.append("\n".join(current).strip())

    return [block for block in blocks if block]


def validate_questions(questions, bt_list, co_list):
    model_name = os.getenv("OLLAMA_MODEL", "mistral")
    count = len(questions)

    prompt = """
You are an academic evaluator.

For each question below, determine whether it matches the requested Bloom's Taxonomy level and Course Outcome (CO). Provide a short justification for each item.
"""

    for idx, (question, bt, co) in enumerate(zip(questions, bt_list, co_list), start=1):
        prompt += f"\nQuestion {idx}: {question}\nTarget Bloom Level: {bt}\nTarget CO: {co}\n"

    prompt += "\nRespond with numbered sections matching each question. Use this format for each item:\nQuestion N:\nBloom Level Match: Yes/No\nCO Match: Yes/No\nReason: [short justification]\n"

    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt
        )

        if response and 'response' in response:
            blocks = _parse_validation_blocks(response['response'])
            if len(blocks) == count:
                return blocks

        # fallback to single item validation if parsing fails
        results = []
        for question, bt, co in zip(questions, bt_list, co_list):
            results.append(validate_question(question, bt, co))

        return results

    except Exception as e:
        return [f"Validation Error: {str(e)}"] * count