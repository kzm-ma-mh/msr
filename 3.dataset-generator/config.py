import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Gitea
    GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000")
    GITEA_TOKEN = os.getenv("GITEA_TOKEN")
    GITEA_API = f"{GITEA_URL}/api/v1"
    GITEA_HEADERS = {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
    }

    # Organization & Repo
    GITEA_ORG = os.getenv("GITEA_ORG", "masir-projects")
    REPO_NAME = "fastapi"

    # Output
    OUTPUT_DIR = "datasets"