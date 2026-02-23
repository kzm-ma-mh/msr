import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ─── Gitea ───
    GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000")
    GITEA_TOKEN = os.getenv("GITEA_TOKEN")
    GITEA_API = f"{GITEA_URL}/api/v1"
    GITEA_HEADERS = {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
    }
    GITEA_ORG = os.getenv("GITEA_ORG", "masir-projects")
    REPO_NAME = os.getenv("REPO_NAME", "fastapi")

    # ─── ChromaDB ───
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

    # ─── Collections (هر نوع داده، collection جدا) ───
    COLLECTION_CODE = os.getenv("COLLECTION_CODE", "code_chunks")
    COLLECTION_ISSUES = os.getenv("COLLECTION_ISSUES", "issue_chunks")
    COLLECTION_PRS = os.getenv("COLLECTION_PRS", "pr_chunks")
    COLLECTION_COMMITS = os.getenv("COLLECTION_COMMITS", "commit_chunks")

    # ─── Embedding ───
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # ─── Chunking ───
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))

    # ─── File Filters ───
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".go", ".rs", ".java",
        ".jsx", ".tsx", ".vue", ".rb", ".php", ".c", ".cpp", ".h",
    }
    DOC_EXTENSIONS = {
        ".md", ".txt", ".rst", ".yaml", ".yml", ".toml", ".json", ".cfg",
    }
    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", "venv",
        ".venv", "dist", "build", ".tox", ".eggs",
        "_crawled_data", ".github",
    }
    MAX_FILE_SIZE = 50_000  # 50KB