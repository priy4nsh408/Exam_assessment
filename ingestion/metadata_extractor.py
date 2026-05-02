
import os
import re


def enrich_metadata(docs):

    for doc in docs:

        # =====================================================
        # GET SOURCE PATH
        # =====================================================
        source = doc.metadata.get("source", "")

        normalized_source = source.replace("\\", "/")

        path_parts = normalized_source.split("/")

        # =====================================================
        # SUBJECT EXTRACTION
        # =====================================================
        subject = "Unknown"

        if "raw" in path_parts:

            raw_index = path_parts.index("raw")

            if raw_index + 1 < len(path_parts):
                subject = path_parts[raw_index + 1]

        elif "pyqs" in path_parts:

            pyq_index = path_parts.index("pyqs")

            if pyq_index + 1 < len(path_parts):
                subject = path_parts[pyq_index + 1]

        # =====================================================
        # UNIT EXTRACTION
        # =====================================================
        unit = "Unknown"

        # 🔹 Try regex first
        match = re.search(
            r'Unit[_ -]?(\d+)',
            normalized_source,
            re.IGNORECASE
        )

        if match:

            unit = f"Unit {match.group(1)}"

        else:

            # 🔹 Try folder name detection
            for part in path_parts:

                if "unit" in part.lower():

                    unit = part.replace("_", " ")

                    break

        # =====================================================
        # SAVE METADATA
        # =====================================================
        doc.metadata["subject"] = subject
        doc.metadata["unit"] = unit

    return docs

