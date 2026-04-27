import re


def enrich_metadata(docs, subject="Unknown"):
    for doc in docs:
        source = doc.metadata.get("source", "")

        match = re.search(r'[Uu]nit[- ]?(\d+)', source)
        if match:
            doc.metadata["unit"] = f"Unit {match.group(1)}"
        else:
            doc.metadata["unit"] = "Unknown"

        doc.metadata["subject"] = subject

    return docs
