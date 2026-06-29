import uuid
import shutil
from pathlib import Path

from groq import Groq, AuthenticationError, APIError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from vector_store import index_pdf, search, delete_document, collection_count
from chatbots import create_bot, get_bot, list_bots, delete_bot, add_doc_to_bot, remove_doc_from_bot

load_dotenv()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="RAG SaaS API", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

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


class CreateBotRequest(BaseModel):
    name: str
    system_prompt: str = ""
    accent_color: str = "#5b7bf5"


class BotChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class KnowledgeBaseRequest(BaseModel):
    doc_id: str
    filename: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def require_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-Id header")
    return x_tenant_id


def _rag_answer(
    query: str,
    tenant_id: str,
    system_prompt: str,
    history: list[dict],
    doc_ids: list[str] | None = None,
    top_k: int = 5,
) -> tuple[str, list[dict]]:
    hits = search(query, tenant_id=tenant_id, top_k=top_k, doc_ids=doc_ids or None)
    context = "\n\n".join(f"[{i+1}] {h['text']}" for i, h in enumerate(hits))

    messages = [{"role": "system", "content": f"{system_prompt}\n\nCONTEXT:\n{context}"}]
    messages += [{"role": h["role"], "content": h["content"]} for h in history[-8:] if h.get("role") != "system"]
    messages.append({"role": "user", "content": query})

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=512,
    )
    return response.choices[0].message.content, hits


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

    try:
        total_chunks = index_pdf(str(save_path), tenant_id=tenant_id, doc_id=doc_id)
    except ValueError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    return {"doc_id": doc_id, "filename": file.filename, "chunks_indexed": total_chunks}


@app.delete("/documents/{doc_id}")
def remove_document(doc_id: str, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    delete_document(tenant_id=tenant_id, doc_id=doc_id)
    (UPLOAD_DIR / tenant_id / f"{doc_id}.pdf").unlink(missing_ok=True)
    return {"deleted": doc_id}


@app.get("/documents/count")
def document_count(x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    return {"chunks_in_store": collection_count(tenant_id)}


# ---------------------------------------------------------------------------
# Search + RAG routes
# ---------------------------------------------------------------------------

@app.post("/search")
def search_endpoint(request: SearchRequest, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    doc_ids = [request.doc_id] if request.doc_id else None
    hits = search(request.query, tenant_id=tenant_id, top_k=request.top_k, doc_ids=doc_ids)
    return {"query": request.query, "results": hits}


@app.post("/rag")
def rag(request: RAGRequest, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    doc_ids = [request.doc_id] if request.doc_id else None
    hits = search(request.query, tenant_id=tenant_id, top_k=request.top_k, doc_ids=doc_ids)
    if not hits:
        raise HTTPException(status_code=404, detail="No documents indexed. Upload a PDF first.")

    context = "\n\n".join(f"[Result {i+1} | Score: {h['score']}]\n{h['text']}" for i, h in enumerate(hits))
    prompt = f"""You are a helpful assistant. Answer using ONLY the context below.
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

    return {"query": request.query, "answer": answer, "sources": hits}


# ---------------------------------------------------------------------------
# Chatbot routes
# ---------------------------------------------------------------------------

@app.post("/chatbots")
def create_chatbot(req: CreateBotRequest, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    return create_bot(tenant_id=tenant_id, name=req.name, system_prompt=req.system_prompt, accent_color=req.accent_color)


@app.get("/chatbots")
def get_chatbots(x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    return list_bots(tenant_id)


@app.get("/chatbots/{bot_id}/config")
def get_chatbot_config(bot_id: str):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"id": bot["id"], "name": bot["name"], "accent_color": bot["accent_color"]}


@app.delete("/chatbots/{bot_id}")
def remove_chatbot(bot_id: str, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    if not delete_bot(bot_id, tenant_id):
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"deleted": bot_id}


# ---------------------------------------------------------------------------
# Knowledge base routes
# ---------------------------------------------------------------------------

@app.post("/chatbots/{bot_id}/knowledge")
def add_knowledge(bot_id: str, req: KnowledgeBaseRequest, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    bot = add_doc_to_bot(bot_id=bot_id, tenant_id=tenant_id, doc_id=req.doc_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"bot_id": bot_id, "doc_ids": bot["doc_ids"]}


@app.delete("/chatbots/{bot_id}/knowledge/{doc_id}")
def remove_knowledge(bot_id: str, doc_id: str, x_tenant_id: str | None = Header(default=None)):
    tenant_id = require_tenant(x_tenant_id)
    bot = remove_doc_from_bot(bot_id=bot_id, tenant_id=tenant_id, doc_id=doc_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"bot_id": bot_id, "doc_ids": bot["doc_ids"]}


# ---------------------------------------------------------------------------
# Public chat endpoint (called by the widget)
# ---------------------------------------------------------------------------

@app.post("/chatbots/{bot_id}/chat")
def chatbot_chat(bot_id: str, req: BotChatRequest):
    bot = get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Use bot's assigned doc_ids as the knowledge base filter (empty = all docs)
    kb_doc_ids = bot.get("doc_ids") or None

    try:
        answer, sources = _rag_answer(
            query=req.message,
            tenant_id=bot["tenant_id"],
            system_prompt=bot["system_prompt"],
            history=req.history,
            doc_ids=kb_doc_ids,
        )
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid GROQ_API_KEY")
    except APIError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"answer": answer, "sources_used": len(sources)}
