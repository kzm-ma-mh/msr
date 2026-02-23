import json
import base64
import time
import requests
from config import Config


class GiteaPusher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.GITEA_HEADERS)

    def _request(self, method, url, **kwargs):
        """درخواست به Gitea API"""
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code in [200, 201, 202, 204]:
            try:
                return resp.json()
            except Exception:
                return {"status": "ok"}
        elif resp.status_code == 409:
            return {"status": "exists"}
        else:
            print(f"❌ Gitea Error {resp.status_code}: {resp.text[:200]}")
            return None

    def ensure_org(self):
        """ساخت Organization اگر وجود نداره"""
        print(f"\n🏢 Ensuring organization: {Config.GITEA_ORG}")
        url = f"{Config.GITEA_API}/orgs/{Config.GITEA_ORG}"
        resp = self.session.get(url)

        if resp.status_code == 200:
            print(f"   ✅ Organization exists")
            return True

        url = f"{Config.GITEA_API}/orgs"
        data = {
            "username": Config.GITEA_ORG,
            "full_name": "Crawled GitHub Projects",
            "description": "Projects crawled from GitHub for training data",
            "visibility": "public",
        }
        result = self._request("POST", url, json=data)
        if result:
            print(f"   ✅ Organization created")
            return True
        return False

    def create_repo(self, repo_name, description=""):
        """ساخت ریپو در Gitea (بدون auto_init برای جلوگیری از مشکل SHA)"""
        print(f"\n📦 Creating repo: {Config.GITEA_ORG}/{repo_name}")

        # اول چک کن وجود داره یا نه
        check_url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}"
        resp = self.session.get(check_url)
        if resp.status_code == 200:
            print(f"   ⚠️ Repo already exists, deleting for fresh start...")
            self._request("DELETE", check_url)
            time.sleep(2)

        # ساخت ریپوی خالی (بدون auto_init)
        url = f"{Config.GITEA_API}/orgs/{Config.GITEA_ORG}/repos"
        data = {
            "name": repo_name,
            "description": description[:255] if description else "",
            "private": False,
            "auto_init": False,
            "default_branch": "main",
        }
        result = self._request("POST", url, json=data)
        if result:
            print(f"   ✅ Repo created (empty)")
            time.sleep(1)

            # یه فایل اولیه بساز تا branch main ایجاد بشه
            init_url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/contents/.gitkeep"
            init_data = {
                "message": "Initial commit",
                "content": base64.b64encode(b"# init").decode("utf-8"),
            }
            self._request("PUT", init_url, json=init_data)
            time.sleep(1)

            return True
        return False

    def _get_file_sha(self, repo_name, filepath):
        """دریافت SHA فایل موجود"""
        url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/contents/{filepath}"
        resp = self.session.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get("sha")
        return None

    def push_file(self, repo_name, filepath, content, message=""):
        """آپلود فایل به ریپو (با مدیریت SHA برای update)"""
        url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/contents/{filepath}"

        # چک کن فایل وجود داره یا نه
        sha = self._get_file_sha(repo_name, filepath)

        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        data = {
            "message": message or f"Add {filepath}",
            "content": encoded,
        }

        # اگه فایل وجود داره، SHA رو اضافه کن
        if sha:
            data["sha"] = sha

        result = self._request("PUT", url, json=data)

        # اگه باز هم خطای SHA داد، یه بار دیگه تلاش کن
        if result is None:
            sha_retry = self._get_file_sha(repo_name, filepath)
            if sha_retry:
                data["sha"] = sha_retry
                result = self._request("PUT", url, json=data)

        return result is not None

    def create_issue(self, repo_name, issue_data):
        """ساخت Issue در Gitea"""
        url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/issues"

        body = issue_data.get("body", "") or ""
        body += f"\n\n---\n"
        body += f"📌 **Original Issue #{issue_data['number']}**\n"
        body += f"🏷️ Labels: {', '.join(issue_data.get('labels', []))}\n"
        body += f"📅 Created: {issue_data.get('created_at', 'N/A')}\n"
        if issue_data.get("closed_at"):
            body += f"✅ Closed: {issue_data['closed_at']}\n"

        data = {
            "title": f"[#{issue_data['number']}] {issue_data['title']}",
            "body": body,
        }

        result = self._request("POST", url, json=data)
        if not result or not result.get("id"):
            return

        gitea_issue_id = result.get("number", result.get("id"))

        # Add comments
        for comment in issue_data.get("comments", []):
            self._add_comment(repo_name, gitea_issue_id, comment)
            time.sleep(0.05)

        # Close if closed
        if issue_data.get("state") == "closed" and gitea_issue_id:
            close_url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/issues/{gitea_issue_id}"
            self._request("PATCH", close_url, json={"state": "closed"})

    def _add_comment(self, repo_name, issue_number, comment):
        """اضافه کردن کامنت به Issue/PR"""
        url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/issues/{issue_number}/comments"

        body = f"**@{comment.get('user', 'unknown')}** ({comment.get('created_at', '')}):\n\n"
        body += comment.get("body", "")

        data = {"body": body}
        self._request("POST", url, json=data)

    def create_pull_request_as_issue(self, repo_name, pr_data):
        """ساخت PR به عنوان Issue (همه اطلاعات diff و review نگه داشته میشه)"""
        url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/issues"

        body = f"## 🔀 Pull Request #{pr_data['number']}\n\n"
        body += pr_data.get("body", "") or ""
        body += f"\n\n---\n"
        body += f"**State:** {'✅ Merged' if pr_data.get('merged') else pr_data.get('state', 'unknown')}\n"
        body += f"**Labels:** {', '.join(pr_data.get('labels', []))}\n"
        body += f"**Created:** {pr_data.get('created_at', 'N/A')}\n"

        if pr_data.get("merged_at"):
            body += f"**Merged:** {pr_data['merged_at']}\n"

        body += f"**Additions:** +{pr_data.get('additions', 0)} "
        body += f"**Deletions:** -{pr_data.get('deletions', 0)}\n"

        # Changed files
        if pr_data.get("changed_files"):
            body += f"\n### 📁 Changed Files ({len(pr_data['changed_files'])})\n\n"
            for f in pr_data["changed_files"]:
                body += f"#### `{f['filename']}` ({f['status']})\n"
                if f.get("patch"):
                    body += f"```diff\n{f['patch'][:3000]}\n```\n\n"

        # Review comments
        if pr_data.get("review_comments"):
            body += f"\n### 💬 Code Review Comments\n\n"
            for r in pr_data["review_comments"]:
                body += f"**@{r['user']}** on `{r.get('path', '')}` ({r.get('created_at', '')}):\n"
                if r.get("diff_hunk"):
                    body += f"```diff\n{r['diff_hunk']}\n```\n"
                body += f"> {r.get('body', '')}\n\n"

        # Truncate if too long
        if len(body) > 60000:
            body = body[:60000] + "\n\n... (truncated)"

        data = {
            "title": f"[PR #{pr_data['number']}] {pr_data['title']}",
            "body": body,
        }

        result = self._request("POST", url, json=data)
        if not result or not result.get("id"):
            return

        gitea_issue_id = result.get("number", result.get("id"))

        # Add comments
        for comment in pr_data.get("comments", []):
            self._add_comment(repo_name, gitea_issue_id, comment)
            time.sleep(0.05)

        # Close if merged/closed
        if pr_data.get("state") == "closed" or pr_data.get("merged"):
            close_url = f"{Config.GITEA_API}/repos/{Config.GITEA_ORG}/{repo_name}/issues/{gitea_issue_id}"
            self._request("PATCH", close_url, json={"state": "closed"})

    def push_crawled_data(self, repo_name, data):
        """پوش کل داده‌های کرول شده به Gitea"""
        print(f"\n{'='*60}")
        print(f"📤 PUSHING TO GITEA: {Config.GITEA_ORG}/{repo_name}")
        print(f"{'='*60}")

        # 1. Create repo
        description = data.get("repo_info", {}).get("description", "")
        self.create_repo(repo_name, description)

        # 2. Push README
        if data.get("readme"):
            print(f"\n📄 Pushing README...")
            self.push_file(repo_name, "README.md", data["readme"], "Add README")

        # 3. Push source files
        source_files = data.get("source_files", [])
        if source_files:
            print(f"\n📁 Pushing {len(source_files)} source files...")
            for i, f in enumerate(source_files):
                self.push_file(
                    repo_name,
                    f["path"],
                    f["content"],
                    f"Add {f['path']}"
                )
                if (i + 1) % 20 == 0:
                    print(f"   ... {i+1}/{len(source_files)}")
                time.sleep(0.1)  # کمی بیشتر صبر کن

        # 4. Push raw data as JSON
        print(f"\n💾 Pushing raw crawled data as JSON...")

        if data.get("issues"):
            issues_json = json.dumps(data["issues"], indent=2, ensure_ascii=False)
            self.push_file(
                repo_name,
                "_crawled_data/issues.json",
                issues_json,
                "Add crawled issues data"
            )

        if data.get("pull_requests"):
            prs_json = json.dumps(data["pull_requests"], indent=2, ensure_ascii=False)
            self.push_file(
                repo_name,
                "_crawled_data/pull_requests.json",
                prs_json,
                "Add crawled pull requests data"
            )

        if data.get("commits"):
            commits_json = json.dumps(data["commits"], indent=2, ensure_ascii=False)
            self.push_file(
                repo_name,
                "_crawled_data/commits.json",
                commits_json,
                "Add crawled commits data"
            )

        repo_meta = json.dumps(data.get("repo_info", {}), indent=2, ensure_ascii=False)
        self.push_file(
            repo_name,
            "_crawled_data/repo_info.json",
            repo_meta,
            "Add repo metadata"
        )

        # 5. Create Issues in Gitea
        issues = data.get("issues", [])
        if issues:
            print(f"\n🐛 Creating {len(issues)} issues in Gitea...")
            for i, issue in enumerate(issues):
                self.create_issue(repo_name, issue)
                if (i + 1) % 50 == 0:
                    print(f"   ... {i+1}/{len(issues)}")
                time.sleep(0.1)

        # 6. Create PRs as Issues in Gitea
        prs = data.get("pull_requests", [])
        if prs:
            print(f"\n🔀 Creating {len(prs)} PRs as issues in Gitea...")
            for i, pr in enumerate(prs):
                self.create_pull_request_as_issue(repo_name, pr)
                if (i + 1) % 50 == 0:
                    print(f"   ... {i+1}/{len(prs)}")
                time.sleep(0.1)

        print(f"\n✅ Done pushing {repo_name} to Gitea!")
        print(f"   🔗 {Config.GITEA_URL}/{Config.GITEA_ORG}/{repo_name}")