import ollama
import os
from dotenv import load_dotenv

load_dotenv()

model_name = os.getenv("OLLAMA_MODEL", "mistral")

res = ollama.generate(
    model=model_name,
    prompt="Say hello"
)

print(res['response'])