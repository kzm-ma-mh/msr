"""
REST API با FastAPI
"""

import json
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rag_engine import RAGEngine
from config import Config


# ─── Pydantic Models ───

class QueryRequest(BaseModel):
    question: str = Field(..., description="سوال کاربر", min_length=3)
    collections: Optional[List[str]] = Field(
        None, description="فیلتر collections: code, issue, pull_request, commit"
    )
    top_k: Optional[int] = Field(None, ge=1, le=20, description="تعداد context")
    temperature: Optional[float] = Field(0.7, ge=0, le=1, description="خلاقیت LLM")


class SearchRequest(BaseModel):
    query: str = Field(..., description="متن جستجو", min_length=2)
    collection: Optional[str] = Field("all", description="collection برای جستجو")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="تعداد نتایج")


class SourceInfo(BaseModel):
    type: str
    score: float
    file: Optional[str] = None
    issue_number: Optional[int] = None
    pr_number: Optional[int] = None
    sha: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    context_length: int
    sources_count: int


class SearchResult(BaseModel):
    content: str
    collection: str
    score: float
    metadata: dict


class StatsResponse(BaseModel):
    llm_model: str
    llm_provider: str
    embedding_model: str
    collections: dict
    total_documents: int


class ModelSwitchRequest(BaseModel):
    model: str = Field(..., description="نام مدل Ollama")


# ─── App ───

app = FastAPI(
    title="LightRAG Code Assistant API",
    description="RAG-based code assistant for repository analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RAG Engine (lazy init)
rag_engine: Optional[RAGEngine] = None


def get_rag() -> RAGEngine:
    """دریافت RAG Engine (Singleton)"""
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
    return rag_engine


# ═══════════════════════════════════════════
#  Health Endpoints
# ═══════════════════════════════════════════

@app.get("/", tags=["Health"])
def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "LightRAG Code Assistant",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    """Health check with details"""
    rag = get_rag()
    stats = rag.get_stats()
    llm_ok = rag.llm.check_connection()

    return {
        "status": "healthy" if llm_ok else "degraded",
        "llm_connected": llm_ok,
        "llm_model": stats["llm_model"],
        "total_documents": stats["total_documents"],
        "collections": stats["collections"],
    }


# ═══════════════════════════════════════════
#  RAG Endpoints
# ═══════════════════════════════════════════

@app.post("/query", response_model=QueryResponse, tags=["RAG"])
def query(request: QueryRequest):
    """
    سوال از RAG

    سوال کاربر رو میگیره، context مرتبط رو از ChromaDB پیدا میکنه،
    و با LLM پاسخ تولید میکنه.
    """
    rag = get_rag()

    result = rag.query(
        question=request.question,
        collections=request.collections,
        top_k=request.top_k,
        temperature=request.temperature,
    )

    return QueryResponse(**result)


@app.post("/query/stream", tags=["RAG"])
def query_stream(request: QueryRequest):
    """
    سوال از RAG بصورت Streaming

    پاسخ رو بصورت Server-Sent Events برمیگردونه.
    """
    rag = get_rag()

    def event_generator():
        for chunk in rag.query_stream(
            question=request.question,
            collections=request.collections,
            top_k=request.top_k,
            temperature=request.temperature,
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ═══════════════════════════════════════════
#  Search Endpoints
# ═══════════════════════════════════════════

@app.post("/search", tags=["Search"])
def search(request: SearchRequest):
    """
    جستجوی معنایی بدون LLM

    فقط context مرتبط رو از ChromaDB برمیگردونه.
    """
    rag = get_rag()

    collections = None
    if request.collection and request.collection != "all":
        collections = [request.collection]

    results = rag.retrieve(
        query=request.query,
        collections=collections,
        top_k=request.top_k,
    )

    return {
        "query": request.query,
        "results": results,
        "total": len(results),
    }


@app.get("/search/code", tags=["Search"])
def search_code(query: str, top_k: int = 5):
    """جستجو در سورس کد"""
    rag = get_rag()
    results = rag.retrieve(query, collections=["code"], top_k=top_k)
    return {"query": query, "results": results, "total": len(results)}


@app.get("/search/issues", tags=["Search"])
def search_issues(query: str, top_k: int = 5):
    """جستجو در Issues"""
    rag = get_rag()
    results = rag.retrieve(query, collections=["issue"], top_k=top_k)
    return {"query": query, "results": results, "total": len(results)}


@app.get("/search/prs", tags=["Search"])
def search_prs(query: str, top_k: int = 5):
    """جستجو در Pull Requests"""
    rag = get_rag()
    results = rag.retrieve(query, collections=["pull_request"], top_k=top_k)
    return {"query": query, "results": results, "total": len(results)}


@app.get("/search/commits", tags=["Search"])
def search_commits(query: str, top_k: int = 5):
    """جستجو در Commits"""
    rag = get_rag()
    results = rag.retrieve(query, collections=["commit"], top_k=top_k)
    return {"query": query, "results": results, "total": len(results)}


# ═══════════════════════════════════════════
#  Model Management Endpoints
# ═══════════════════════════════════════════

@app.get("/model/current", tags=["Model"])
def current_model():
    """نمایش مدل فعلی"""
    rag = get_rag()
    return {
        "model": rag.llm.model,
        "provider": rag.llm.provider,
        "base_url": rag.llm.base_url,
    }


@app.get("/model/list", tags=["Model"])
def list_models():
    """لیست مدل‌های موجود در Ollama"""
    rag = get_rag()
    try:
        resp = rag.llm.session.get(f"{rag.llm.base_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return {
                "models": [
                    {
                        "name": m.get("name", ""),
                        "size": f"{m.get('size', 0) / (1024**3):.1f} GB",
                        "modified": m.get("modified_at", ""),
                    }
                    for m in models
                ]
            }
        return {"models": [], "error": "Cannot fetch models"}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.post("/model/switch", tags=["Model"])
def switch_model(request: ModelSwitchRequest):
    """
    تغییر مدل LLM بدون restart

    مدل‌های موجود رو از /model/list ببینید.
    """
    rag = get_rag()
    old_model = rag.llm.model
    rag.llm.model = request.model

    # چک اتصال
    connected = rag.llm.check_connection()

    # اگه مدل پیدا نشد، برگرد به قبلی
    if not connected:
        rag.llm.model = old_model
        return {
            "success": False,
            "error": f"Model '{request.model}' not available",
            "current_model": old_model,
        }

    return {
        "success": True,
        "old_model": old_model,
        "new_model": request.model,
        "connected": connected,
    }


# ═══════════════════════════════════════════
#  System Endpoints
# ═══════════════════════════════════════════

@app.get("/stats", response_model=StatsResponse, tags=["System"])
def stats():
    """آمار سیستم"""
    rag = get_rag()
    return rag.get_stats()


@app.get("/collections", tags=["System"])
def collections():
    """لیست collections"""
    rag = get_rag()
    st = rag.get_stats()
    return {
        "collections": [
            {"name": name, "count": count}
            for name, count in st["collections"].items()
        ]
    }