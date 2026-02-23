"""
بارگذاری داده‌ها از backup محلی یا Gitea API
"""

import json
import os
import base64
import requests
from config import Config


class GiteaDataLoader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.GITEA_HEADERS)

        # اول چک کن backup محلی هست یا نه
        self.backup_file = self._find_backup()
        self.backup_data = None

        if self.backup_file:
            print(f"📂 Using local backup: {self.backup_file}")
            with open(self.backup_file, "r", encoding="utf-8") as f:
                self.backup_data = json.load(f)
        else:
            print(f"🌐 Using Gitea API: {Config.GITEA_URL}")

    def _find_backup(self):
        """پیدا کردن فایل backup"""
        possible_paths = [
            # همین پوشه
            f"crawled_data_backup/{Config.REPO_NAME}_fastapi.json",
            f"crawled_data_backup/fastapi_{Config.REPO_NAME}.json",
            f"crawled_data_backup/fastapi_fastapi.json",
            # پوشه بالاتر (crawler)
            f"../github-to-gitea-crawler/crawled_data_backup/fastapi_fastapi.json",
            # مسیر مستقیم
            f"../crawled_data_backup/fastapi_fastapi.json",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # جستجوی عمومی
        for root, dirs, files in os.walk(".."):
            for f in files:
                if f == "fastapi_fastapi.json":
                    return os.path.join(root, f)

        return None

    def _api(self, endpoint, params=None):
        """درخواست به Gitea API"""
        url = f"{Config.GITEA_API}{endpoint}"
        resp = self.session.get(url, params=params)
        if resp.status_code == 200:
            return resp.json()
        return None

    def _get_file_content(self, path):
        """دریافت محتوای یک فایل از Gitea"""
        endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/contents/{path}"
        data = self._api(endpoint)
        if data and data.get("content"):
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except Exception:
                return None
        return None

    def _list_files_recursive(self, path=""):
        """لیست بازگشتی فایل‌ها از Gitea"""
        endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/contents/{path}"
        data = self._api(endpoint)
        if not data or not isinstance(data, list):
            return []

        files = []
        for item in data:
            name = item.get("name", "")
            item_path = item.get("path", "")

            if item["type"] == "file":
                files.append({
                    "path": item_path,
                    "size": item.get("size", 0),
                    "name": name,
                })
            elif item["type"] == "dir":
                if name not in Config.SKIP_DIRS:
                    files.extend(self._list_files_recursive(item_path))

        return files

    # ─── Public Methods ───

    def load_source_files(self):
        """بارگذاری فایل‌های سورس کد"""
        print("\n📁 Loading source files...")

        # از backup
        if self.backup_data and self.backup_data.get("source_files"):
            files = self.backup_data["source_files"]
            source_files = []
            for sf in files:
                path = sf.get("path", "")
                content = sf.get("content", "")
                if content and len(content.strip()) > 20:
                    ext = path.rsplit(".", 1)[-1] if "." in path else "unknown"
                    source_files.append({
                        "path": path,
                        "content": content,
                        "language": ext,
                    })
            print(f"   ✅ Loaded {len(source_files)} files (from backup)")
            return source_files

        # از Gitea API
        print("   Loading from Gitea API...")
        all_files = self._list_files_recursive()

        valid_extensions = Config.CODE_EXTENSIONS | Config.DOC_EXTENSIONS
        filtered = []
        for f in all_files:
            ext = ""
            if "." in f["name"]:
                ext = "." + f["name"].rsplit(".", 1)[-1].lower()
            if ext not in valid_extensions:
                continue
            if f["size"] > Config.MAX_FILE_SIZE:
                continue
            filtered.append(f)

        print(f"   Found {len(filtered)} files")

        source_files = []
        for f in filtered:
            content = self._get_file_content(f["path"])
            if content and len(content.strip()) > 20:
                ext = f["path"].rsplit(".", 1)[-1] if "." in f["path"] else "unknown"
                source_files.append({
                    "path": f["path"],
                    "content": content,
                    "language": ext,
                })

        print(f"   ✅ Loaded {len(source_files)} files (from API)")
        return source_files

    def load_issues(self):
        """بارگذاری Issues"""
        print("\n🐛 Loading issues...")

        # از backup
        if self.backup_data and self.backup_data.get("issues"):
            issues = self.backup_data["issues"]
            print(f"   ✅ Loaded {len(issues)} issues (from backup)")
            return issues

        # از Gitea API
        content = self._get_file_content("_crawled_data/issues.json")
        if not content:
            print("   ⚠️ No issues found")
            return []

        issues = json.loads(content)
        print(f"   ✅ Loaded {len(issues)} issues (from API)")
        return issues

    def load_pull_requests(self):
        """بارگذاری Pull Requests"""
        print("\n🔀 Loading pull requests...")

        # از backup
        if self.backup_data and self.backup_data.get("pull_requests"):
            prs = self.backup_data["pull_requests"]
            print(f"   ✅ Loaded {len(prs)} pull requests (from backup)")
            return prs

        # از Gitea API
        content = self._get_file_content("_crawled_data/pull_requests.json")
        if not content:
            print("   ⚠️ No pull requests found")
            return []

        prs = json.loads(content)
        print(f"   ✅ Loaded {len(prs)} pull requests (from API)")
        return prs

    def load_commits(self):
        """بارگذاری Commits"""
        print("\n📝 Loading commits...")

        # از backup
        if self.backup_data and self.backup_data.get("commits"):
            commits = self.backup_data["commits"]
            print(f"   ✅ Loaded {len(commits)} commits (from backup)")
            return commits

        # از Gitea API
        content = self._get_file_content("_crawled_data/commits.json")
        if not content:
            print("   ⚠️ No commits found")
            return []

        commits = json.loads(content)
        print(f"   ✅ Loaded {len(commits)} commits (from API)")
        return commits