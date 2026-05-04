import os
import re
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


def _parse_questions(response):
    items = []
    current = []

    for line in response.splitlines():
        text = line.strip()
        if not text:
            continue

        match = re.match(r'^(?:\d+[\.)]\s*|[-*]\s*)(.*)$', text)
        if match:
            if current:
                items.append(" ".join(current).strip())
            current = [match.group(1).strip()]
        else:
            if current:
                current.append(text)
            else:
                current = [text]

    if current:
        items.append(" ".join(current).strip())

    return [item for item in items if item]


def generate_questions(context, example, bt_list, co_list):
    example_question = example.get("question", "No example provided")
    model_name = os.getenv("OLLAMA_MODEL", "mistral")
    count = len(bt_list)

    requirements = []
    for idx, (bt, co) in enumerate(zip(bt_list, co_list), start=1):
        requirements.append(f"{idx}. Bloom Level: {bt}, CO: {co}")

    prompt = f"""
You are an expert engineering question paper setter.

Your task is to generate {count} HIGH-QUALITY, ORIGINAL exam questions.

CONTEXT:
{context}

REFERENCE QUESTION (DO NOT COPY):
{example_question}

REQUIREMENTS:
"""

    for line in requirements:
        prompt += f"- {line}\n"

    prompt += "\nReturn ONLY the questions as a numbered list, one question per prompt item. Do not include any extra commentary."

    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt
        )

        if response and 'response' in response:
            questions = _parse_questions(response['response'])
            if len(questions) == count:
                return questions
            if questions:
                return questions[:count]
            return [response['response'].strip()]

        return ["Generation Error: Empty response"] * count

    except Exception as e:
        return [f"Generation Error: {str(e)}"] * count
