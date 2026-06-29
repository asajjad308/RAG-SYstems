import chromadb
from chromadb.config import Settings
from embeddings import get_model, load_embeddings
from chunker import chunk_pdf

COLLECTION_NAME = "remediation_tasks"

_client = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path="./chroma_db")
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index_pdf(pdf_path: str) -> int:
    chunks = chunk_pdf(pdf_path)
    model = get_model()

    texts = [c["text"] for c in chunks]
    vectors = model.encode(texts, show_progress_bar=False).tolist()
    ids = [str(c["id"]) for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    collection = get_collection()
    collection.upsert(
        ids=ids,
        embeddings=vectors,
        documents=texts,
        metadatas=metadatas,
    )
    return len(chunks)


def search(query: str, top_k: int = 5) -> list[dict]:
    model = get_model()
    query_vector = model.encode([query]).tolist()

    collection = get_collection()
    results = collection.query(
        query_embeddings=query_vector,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text": doc,
            "metadata": meta,
            "score": round(1 - dist, 4),  # cosine similarity
        })
    return hits


def collection_count() -> int:
    return get_collection().count()
