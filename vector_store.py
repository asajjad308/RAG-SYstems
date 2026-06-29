import chromadb
from embeddings import get_model
from chunker import chunk_pdf

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path="./chroma_db")
    return _client


def get_collection(tenant_id: str):
    return get_client().get_or_create_collection(
        name=f"tenant_{tenant_id}",
        metadata={"hnsw:space": "cosine"},
    )


def index_pdf(pdf_path: str, tenant_id: str, doc_id: str) -> int:
    chunks = chunk_pdf(pdf_path)
    if not chunks:
        raise ValueError("No text could be extracted from this PDF")
    model = get_model()

    texts     = [c["text"] for c in chunks]
    vectors   = model.encode(texts, show_progress_bar=False).tolist()
    ids       = [f"{doc_id}_{c['id']}" for c in chunks]
    metadatas = [{**c["metadata"], "doc_id": doc_id} for c in chunks]

    get_collection(tenant_id).upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
    return len(chunks)


def search(query: str, tenant_id: str, top_k: int = 5, doc_ids: list[str] | None = None) -> list[dict]:
    model = get_model()
    query_vector = model.encode([query]).tolist()

    # Build ChromaDB where filter
    if doc_ids and len(doc_ids) == 1:
        where = {"doc_id": doc_ids[0]}
    elif doc_ids and len(doc_ids) > 1:
        where = {"doc_id": {"$in": doc_ids}}
    else:
        where = None

    collection = get_collection(tenant_id)

    # n_results can't exceed collection size
    count = collection.count()
    if count == 0:
        return []
    n = min(top_k, count)

    results = collection.query(
        query_embeddings=query_vector,
        n_results=n,
        include=["documents", "metadatas", "distances"],
        where=where,
    )

    return [
        {"text": doc, "metadata": meta, "score": round(1 - dist, 4)}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def delete_document(tenant_id: str, doc_id: str):
    collection = get_collection(tenant_id)
    existing = collection.get(where={"doc_id": doc_id})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])


def collection_count(tenant_id: str) -> int:
    return get_collection(tenant_id).count()
