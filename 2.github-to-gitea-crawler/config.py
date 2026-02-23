import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # GitHub
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_API = "https://api.github.com"
    GITHUB_HEADERS = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Gitea
    GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000")
    GITEA_TOKEN = os.getenv("GITEA_TOKEN")
    GITEA_API = f"{GITEA_URL}/api/v1"
    GITEA_HEADERS = {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
    }

    # Repos
    GITHUB_REPOS = [
        r.strip() for r in os.getenv("GITHUB_REPOS", "").split(",") if r.strip()
    ]

    # Gitea Organization
    GITEA_ORG = os.getenv("GITEA_ORG", "crawled-projects")

    # Crawl settings
    MAX_ISSUES = 500        # حداکثر تعداد issue
    MAX_PRS = 500           # حداکثر تعداد PR
    MAX_COMMENTS = 50       # حداکثر کامنت هر issue/PR
    PER_PAGE = 100          # تعداد آیتم در هر صفحه API