
def retrieve_context(
    vectordb,
    query,
    subject=None,
    unit=None,
    k=5,
    raise_on_error=False
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

    raise_on_error : bool
        By default (False), any error during retrieval (including an
        embedding-model failure, e.g. no network access to download it) is
        swallowed and "" is returned, matching this function's original
        behavior for app/main.py and app/streamlit_app.py. Set True to
        instead re-raise the real exception - used by the generation
        pipeline (generation/langgraph_pipeline.py's scout_agent) so an
        embedding-model failure can be reported as exactly that, rather
        than being silently misreported as "no matching documents found"
        (which was actively misleading - the embedding model failing to
        load and the collection genuinely having no matching content are
        very different problems requiring very different fixes).

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

        if raise_on_error:
            raise

        return ""

