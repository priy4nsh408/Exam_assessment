# AI Exam System

This project is a Python-based AI exam generation system with a command-line interface and a new Streamlit frontend.

## Frontend

A Streamlit UI has been added at `app/streamlit_app.py`.

### Run the frontend

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the Streamlit app:
   ```bash
   streamlit run app/streamlit_app.py
   ```

### What the frontend supports

- Subject selection from `data/raw`
- Automatic document loading, metadata enrichment, and chunking
- Semantic search by unit and optional topic query
- PYQ set selection from `data/pyqs`
- Bloom level and CO selection
- Question generation and validation using your existing AI pipeline

## Notes

- Ensure `OLLAMA_MODEL` is configured in your `.env` file.
- The app will create or reuse subject-specific Chroma vector stores under `data/db/chroma/`.
