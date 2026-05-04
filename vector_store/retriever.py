
def retrieve_context(
    vectordb,
    query,
    subject=None,
    unit=None,
    k=5
):
    """
    Retrieve relevant context from ChromaDB

    Parameters:
    ---------------------------------
    vectordb : Chroma object

    query : str
        User query/topic

    subject : str
        Optional subject filter

    unit : str
        Optional unit filter

    k : int
        Number of chunks to retrieve

    Returns:
    ---------------------------------
    context : str
    """

    try:

        # =================================================
        # BUILD FILTER
        # =================================================
        if subject and unit:
            filters = {
                "$and": [
                    {"subject": {"$eq": subject}},
                    {"unit": {"$eq": unit}}
                ]
            }
        elif subject:
            filters = {"subject": {"$eq": subject}}
        elif unit:
            filters = {"unit": {"$eq": unit}}
        else:
            filters = {}

        # Debug filter format
        if filters:
            print(f"🔧 Chroma where filter: {filters}")

        # =================================================
        # RETRIEVE DOCUMENTS
        # =================================================
        if filters:
            docs = vectordb.similarity_search(
                query,
                k=k,
                filter=filters
            )

        else:

            docs = vectordb.similarity_search(
                query,
                k=k
            )

        # =================================================
        # NO RESULTS
        # =================================================
        if not docs:

            print("⚠️ No matching documents found")

            return ""

        # =================================================
        # DEBUG INFO
        # =================================================
        print(
            f"\n🔍 Retrieved {len(docs)} chunks"
        )

        # =================================================
        # COMBINE CONTEXT
        # =================================================
        context = "\n\n".join([
            doc.page_content
            for doc in docs
        ])

        return context

    except Exception as e:

        print(f"❌ Retrieval Error: {e}")

        return ""

