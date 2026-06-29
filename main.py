import uuid
import shutil
from pathlib import Path

from groq import Groq, AuthenticationError, APIError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from vector_store import index_pdf, search, delete_document, collection_count

load_dotenv()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="RAG SaaS API", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
groq_client = Groq()


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    doc_id: str | None = None


class RAGRequest(BaseModel):
    query: str
    top_k: int = 5
    doc_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def require_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")
    return x_tenant_id


# ---------------------------------------------------------------------------
# Document routes
# ---------------------------------------------------------------------------

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(default=None),
):
    tenant_id = require_tenant(x_tenant_id)

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    save_path = tenant_dir / f"{doc_id}.pdf"

    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Chunk + embed + index into ChromaDB
    try:
        total_chunks = index_pdf(str(save_path), tenant_id=tenant_id, doc_id=doc_id)
    except ValueError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "chunks_indexed": total_chunks,
        "tenant_id": tenant_id,
    }


@app.delete("/documents/{doc_id}")
def remove_document(
    doc_id: str,
    x_tenant_id: str | None = Header(default=None),
):
    tenant_id = require_tenant(x_tenant_id)
    delete_document(tenant_id=tenant_id, doc_id=doc_id)

    # Remove file from disk
    tenant_dir = UPLOAD_DIR / tenant_id
    for f in tenant_dir.glob(f"{doc_id}.pdf"):
        f.unlink(missing_ok=True)

    return {"deleted": doc_id}


@app.get("/documents/count")
def document_count(x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    return {"chunks_in_store": collection_count(tenant_id), "tenant_id": tenant_id}


# ---------------------------------------------------------------------------
# Search + RAG routes
# ---------------------------------------------------------------------------

@app.post("/search")
def search_endpoint(
    request: SearchRequest,
    x_tenant_id: str | None = Header(default=None),
):
    tenant_id = require_tenant(x_tenant_id)
    hits = search(request.query, tenant_id=tenant_id, top_k=request.top_k, doc_id=request.doc_id)
    return {"query": request.query, "results": hits}


@app.post("/rag")
def rag(
    request: RAGRequest,
    x_tenant_id: str | None = Header(default=None),
):
    tenant_id = require_tenant(x_tenant_id)

    # 1. Retrieve
    hits = search(request.query, tenant_id=tenant_id, top_k=request.top_k, doc_id=request.doc_id)
    if not hits:
        raise HTTPException(status_code=404, detail="No documents indexed. Upload a PDF first via POST /documents/upload")

    # 2. Build context
    context = "\n\n".join(
        f"[Result {i+1} | Score: {h['score']}]\n{h['text']}"
        for i, h in enumerate(hits)
    )

    # 3. Generate
    prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "I don't have enough information."

CONTEXT:
{context}

QUESTION: {request.query}

ANSWER:"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        answer = response.choices[0].message.content
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid GROQ_API_KEY in .env")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "query": request.query,
        "answer": answer,
        "sources": hits,
        "tenant_id": tenant_id,
    }
