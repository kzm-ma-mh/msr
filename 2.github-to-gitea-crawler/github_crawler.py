import time
import requests
from tqdm import tqdm
from config import Config


class GitHubCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.GITHUB_HEADERS)

    def _request(self, url, params=None):
        """درخواست با مدیریت rate limit"""
        while True:
            resp = self.session.get(url, params=params)

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 403:
                reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_time - int(time.time()), 10)
                print(f"⏳ Rate limit! Waiting {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 404:
                print(f"⚠️ Not found: {url}")
                return None

            print(f"❌ Error {resp.status_code}: {url}")
            return None

    def _paginate(self, url, params=None, max_items=None):
        """دریافت صفحه‌بندی شده"""
        if params is None:
            params = {}
        params["per_page"] = Config.PER_PAGE
        params["page"] = 1

        all_items = []
        while True:
            data = self._request(url, params)
            if not data:
                break

            all_items.extend(data)

            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break

            if len(data) < Config.PER_PAGE:
                break

            params["page"] += 1

        return all_items

    def get_repo_info(self, owner, repo):
        """اطلاعات کلی ریپو"""
        print(f"\n📦 Getting repo info: {owner}/{repo}")
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}"
        return self._request(url)

    def get_readme(self, owner, repo):
        """دریافت README"""
        print(f"📄 Getting README...")
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/readme"
        data = self._request(url)
        if data and "content" in data:
            import base64
            try:
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            except Exception:
                return None
        return None

    def get_file_tree(self, owner, repo, branch="main"):
        """دریافت ساختار فایل‌ها"""
        print(f"🌳 Getting file tree...")
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}"
        data = self._request(url, params={"recursive": "1"})

        if not data:
            # Try 'master' branch
            url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/git/trees/master"
            data = self._request(url, params={"recursive": "1"})

        if data and "tree" in data:
            return data["tree"]
        return []

    def get_file_content(self, owner, repo, path):
        """دریافت محتوای یک فایل"""
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        data = self._request(url)
        if data and "content" in data:
            import base64
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except Exception:
                return None
        return None

    def get_source_files(self, owner, repo, branch="main"):
        """دریافت فایل‌های سورس کد (فقط فایل‌های مهم)"""
        print(f"📁 Getting source files...")

        EXTENSIONS = {
            ".py", ".js", ".ts", ".go", ".rs", ".java",
            ".md", ".txt", ".yaml", ".yml", ".toml",
            ".json", ".sh", ".dockerfile",
        }

        SKIP_DIRS = {
            "node_modules", ".git", "__pycache__", "venv",
            ".venv", "dist", "build", ".tox", ".eggs",
        }

        MAX_FILE_SIZE = 100_000  # 100KB max
        MAX_FILES = 200

        tree = self.get_file_tree(owner, repo, branch)
        files = []

        candidates = []
        for item in tree:
            if item["type"] != "blob":
                continue

            path = item["path"]

            # Skip unwanted directories
            parts = path.split("/")
            if any(d in SKIP_DIRS for d in parts):
                continue

            # Check extension
            ext = ""
            if "." in path.split("/")[-1]:
                ext = "." + path.split("/")[-1].rsplit(".", 1)[-1].lower()

            if ext not in EXTENSIONS:
                continue

            size = item.get("size", 0)
            if size > MAX_FILE_SIZE:
                continue

            candidates.append(path)

        candidates = candidates[:MAX_FILES]

        print(f"   📥 Downloading {len(candidates)} files...")
        for path in tqdm(candidates, desc="   Files"):
            content = self.get_file_content(owner, repo, path)
            if content:
                files.append({"path": path, "content": content})
            time.sleep(0.1)  # Be nice to API

        return files

    def get_issues(self, owner, repo):
        """دریافت Issues با کامنت‌ها"""
        print(f"🐛 Getting issues (max {Config.MAX_ISSUES})...")
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/issues"
        params = {"state": "all", "sort": "comments", "direction": "desc"}

        raw_issues = self._paginate(url, params, max_items=Config.MAX_ISSUES)

        # Filter out PRs (GitHub returns PRs in issues endpoint too)
        raw_issues = [i for i in raw_issues if "pull_request" not in i]

        issues = []
        for issue in tqdm(raw_issues, desc="   Issues"):
            issue_data = {
                "number": issue["number"],
                "title": issue["title"],
                "body": issue.get("body", "") or "",
                "state": issue["state"],
                "labels": [l["name"] for l in issue.get("labels", [])],
                "created_at": issue["created_at"],
                "closed_at": issue.get("closed_at"),
                "comments": [],
            }

            # Get comments
            if issue.get("comments", 0) > 0:
                comments_url = issue["comments_url"]
                comments = self._paginate(
                    comments_url, max_items=Config.MAX_COMMENTS
                )
                for c in comments:
                    issue_data["comments"].append({
                        "user": c["user"]["login"],
                        "body": c.get("body", "") or "",
                        "created_at": c["created_at"],
                    })

            issues.append(issue_data)
            time.sleep(0.05)

        print(f"   ✅ Got {len(issues)} issues")
        return issues

    def get_pull_requests(self, owner, repo):
        """دریافت Pull Requests با diff و review comments"""
        print(f"🔀 Getting pull requests (max {Config.MAX_PRS})...")
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/pulls"
        params = {"state": "all", "sort": "updated", "direction": "desc"}

        raw_prs = self._paginate(url, params, max_items=Config.MAX_PRS)

        prs = []
        for pr in tqdm(raw_prs, desc="   PRs"):
            pr_data = {
                "number": pr["number"],
                "title": pr["title"],
                "body": pr.get("body", "") or "",
                "state": pr["state"],
                "merged": pr.get("merged_at") is not None,
                "labels": [l["name"] for l in pr.get("labels", [])],
                "created_at": pr["created_at"],
                "merged_at": pr.get("merged_at"),
                "closed_at": pr.get("closed_at"),
                "diff": None,
                "comments": [],
                "review_comments": [],
                "changed_files": [],
            }

            # Get PR details (diff)
            pr_detail_url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/pulls/{pr['number']}"
            pr_detail = self._request(pr_detail_url)
            if pr_detail:
                pr_data["additions"] = pr_detail.get("additions", 0)
                pr_data["deletions"] = pr_detail.get("deletions", 0)
                pr_data["changed_files_count"] = pr_detail.get("changed_files", 0)

            # Get PR files (changes)
            files_url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/pulls/{pr['number']}/files"
            files = self._paginate(files_url, max_items=30)
            for f in files:
                pr_data["changed_files"].append({
                    "filename": f["filename"],
                    "status": f["status"],  # added, removed, modified
                    "additions": f["additions"],
                    "deletions": f["deletions"],
                    "patch": f.get("patch", "")[:5000],  # Limit patch size
                })

            # Get comments
            comments_url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/issues/{pr['number']}/comments"
            comments = self._paginate(comments_url, max_items=Config.MAX_COMMENTS)
            for c in comments:
                pr_data["comments"].append({
                    "user": c["user"]["login"],
                    "body": c.get("body", "") or "",
                    "created_at": c["created_at"],
                })

            # Get review comments (inline code reviews)
            review_url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/pulls/{pr['number']}/comments"
            reviews = self._paginate(review_url, max_items=Config.MAX_COMMENTS)
            for r in reviews:
                pr_data["review_comments"].append({
                    "user": r["user"]["login"],
                    "body": r.get("body", "") or "",
                    "path": r.get("path", ""),
                    "diff_hunk": r.get("diff_hunk", ""),
                    "created_at": r["created_at"],
                })

            prs.append(pr_data)
            time.sleep(0.1)

        print(f"   ✅ Got {len(prs)} pull requests")
        return prs

    def get_commits(self, owner, repo, max_commits=200):
        """دریافت Commits مهم"""
        print(f"📝 Getting commits (max {max_commits})...")
        url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/commits"

        raw_commits = self._paginate(url, max_items=max_commits)

        commits = []
        for c in tqdm(raw_commits, desc="   Commits"):
            commit_data = {
                "sha": c["sha"][:8],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            }

            # Get commit detail (changed files)
            detail_url = f"{Config.GITHUB_API}/repos/{owner}/{repo}/commits/{c['sha']}"
            detail = self._request(detail_url)
            if detail and "files" in detail:
                commit_data["files"] = []
                for f in detail["files"][:20]:  # Max 20 files per commit
                    commit_data["files"].append({
                        "filename": f["filename"],
                        "status": f["status"],
                        "additions": f["additions"],
                        "deletions": f["deletions"],
                        "patch": f.get("patch", "")[:3000],
                    })

            commits.append(commit_data)
            time.sleep(0.1)

        print(f"   ✅ Got {len(commits)} commits")
        return commits

    def crawl_repo(self, owner, repo):
        """کرول کامل یک ریپو"""
        print(f"\n{'='*60}")
        print(f"🚀 CRAWLING: {owner}/{repo}")
        print(f"{'='*60}")

        repo_info = self.get_repo_info(owner, repo)
        if not repo_info:
            print(f"❌ Failed to get repo info for {owner}/{repo}")
            return None

        default_branch = repo_info.get("default_branch", "main")

        data = {
            "repo_info": {
                "full_name": repo_info["full_name"],
                "description": repo_info.get("description", ""),
                "language": repo_info.get("language", ""),
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "default_branch": default_branch,
                "topics": repo_info.get("topics", []),
            },
            "readme": self.get_readme(owner, repo),
            "source_files": self.get_source_files(owner, repo, default_branch),
            "issues": self.get_issues(owner, repo),
            "pull_requests": self.get_pull_requests(owner, repo),
            "commits": self.get_commits(owner, repo),
        }

        # Summary
        print(f"\n📊 Summary for {owner}/{repo}:")
        print(f"   📁 Source files: {len(data['source_files'])}")
        print(f"   🐛 Issues: {len(data['issues'])}")
        print(f"   🔀 Pull Requests: {len(data['pull_requests'])}")
        print(f"   📝 Commits: {len(data['commits'])}")

        return data