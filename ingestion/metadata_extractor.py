import re

def enrich_metadata(docs):
    for doc in docs:
        source = doc.metadata.get("source", "")

        # 🔍 Extract unit number using regex
        match = re.search(r'Unit[- ]?(\d+)', source, re.IGNORECASE)

        if match:
            doc.metadata["unit"] = f"Unit {match.group(1)}"
        else:
            doc.metadata["unit"] = "Unknown"

        doc.metadata["subject"] = "BDT"

    return docs