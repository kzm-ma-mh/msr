import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ─── Gitea ───
    GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000")
    GITEA_TOKEN = os.getenv("GITEA_TOKEN")
    GITEA_ORG = os.getenv("GITEA_ORG", "masir-projects")
    REPO_NAME = os.getenv("REPO_NAME", "fastapi")

    # ─── LLM ───
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "my_finetuned_model")

    # ─── ChromaDB ───
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "../vector-db/chroma_data")

    # ─── Collections ───
    COLLECTION_CODE = os.getenv("COLLECTION_CODE", "code_chunks")
    COLLECTION_ISSUES = os.getenv("COLLECTION_ISSUES", "issue_chunks")
    COLLECTION_PRS = os.getenv("COLLECTION_PRS", "pr_chunks")
    COLLECTION_COMMITS = os.getenv("COLLECTION_COMMITS", "commit_chunks")

    # ─── Embedding ───
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # ─── API ───
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))

    # ─── RAG ───
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", 8))
    RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", 0.3))
    RAG_MAX_CONTEXT_LENGTH = int(os.getenv("RAG_MAX_CONTEXT_LENGTH", 4000))

    # ─── System Prompt ───
    SYSTEM_PROMPT = """You are an expert code assistant with deep knowledge of the repository.
You have access to the codebase, issues, pull requests, and commits.

When answering:
1. Be specific and reference actual code, files, or issues when possible
2. Provide code examples when relevant
3. If you're not sure, say so
4. Keep answers concise but complete

Repository: {repo_name}
"""