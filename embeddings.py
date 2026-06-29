import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
from chunker import chunk_pdf

MODEL_NAME = "all-MiniLM-L6-v2"
STORE_PATH = Path("embeddings_store.json")

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def create_embeddings(pdf_path: str) -> list[dict]:
    chunks = chunk_pdf(pdf_path)
    model = get_model()

    texts = [c["text"] for c in chunks]
    vectors = model.encode(texts, show_progress_bar=False).tolist()

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    # Persist to disk
    STORE_PATH.write_text(json.dumps(chunks, indent=2))

    return chunks


def load_embeddings() -> list[dict]:
    if not STORE_PATH.exists():
        return []
    return json.loads(STORE_PATH.read_text())
