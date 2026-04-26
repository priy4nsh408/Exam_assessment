def retrieve_context(vectordb, query):
    docs = vectordb.similarity_search(query, k=3)
    return "\n".join([doc.page_content for doc in docs])