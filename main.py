from groq import Groq, AuthenticationError, APIError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from chunker import chunk_pdf
from embeddings import create_embeddings, load_embeddings
from vector_store import index_pdf, search, collection_count

load_dotenv()

app = FastAPI()
client = Groq()  # reads GROQ_API_KEY from .env


class ChatRequest(BaseModel):
    message: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/chunk-pdf")
def chunk_pdf_endpoint():
    chunks = chunk_pdf("files/BullsAI_Remediation_Tasks_MustHave.pdf")
    return {"total": len(chunks), "chunks": chunks}


@app.post("/embed")
def embed_pdf():
    chunks = create_embeddings("files/BullsAI_Remediation_Tasks_MustHave.pdf")
    return {
        "total": len(chunks),
        "model": "all-MiniLM-L6-v2",
        "dimensions": len(chunks[0]["embedding"]) if chunks else 0,
        "saved_to": "embeddings_store.json",
    }


@app.get("/embeddings")
def get_embeddings():
    chunks = load_embeddings()
    return {"total": len(chunks), "chunks": chunks}


@app.post("/index")
def index_to_vectordb():
    total = index_pdf("files/BullsAI_Remediation_Tasks_MustHave.pdf")
    return {
        "indexed": total,
        "collection": "remediation_tasks",
        "stored_in": "./chroma_db",
    }


@app.post("/search")
def search_endpoint(request: SearchRequest):
    hits = search(request.query, top_k=request.top_k)
    return {"query": request.query, "results": hits}


@app.get("/vectordb/count")
def vectordb_count():
    return {"count": collection_count()}


@app.post("/rag")
def rag(request: SearchRequest):
    # 1. Retrieve relevant chunks from ChromaDB
    hits = search(request.query, top_k=request.top_k)
    if not hits:
        raise HTTPException(status_code=404, detail="No relevant documents found. Run POST /index first.")

    # 2. Build context from retrieved chunks
    context = "\n\n".join(
        f"[Task {i+1} | Score: {h['score']}]\n{h['text']}"
        for i, h in enumerate(hits)
    )

    # 3. Generate answer with Groq using retrieved context
    prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't have enough information."

CONTEXT:
{context}

QUESTION: {request.query}

ANSWER:"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        answer = response.choices[0].message.content
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key — set GROQ_API_KEY in .env")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "query": request.query,
        "answer": answer,
        "sources": hits,
    }


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": request.message}],
            max_tokens=1024,
        )
        return {"response": response.choices[0].message.content}
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key — set GROQ_API_KEY in .env")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))
