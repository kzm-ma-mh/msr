#!/usr/bin/env python3
"""
Push crawled data from local backup to Gitea
Uses git clone/push for files (no SHA issues)
Uses API for issues/PRs
"""

import json
import os
import shutil
import subprocess
import time
import requests
from config import Config


class GiteaSmartPusher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.GITEA_HEADERS)

    def _api(self, method, endpoint, **kwargs):
        """درخواست به Gitea API"""
        url = f"{Config.GITEA_API}{endpoint}"
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code in [200, 201, 202, 204]:
            try:
                return resp.json()
            except Exception:
                return {"status": "ok"}
        elif resp.status_code == 409:
            return {"status": "exists"}
        else:
            print(f"   ❌ API Error {resp.status_code}: {resp.text[:200]}")
            return None

    def delete_repo_if_exists(self, repo_name):
        """پاک کردن ریپوی قبلی"""
        print(f"\n🗑️ Checking if repo exists...")
        endpoint = f"/repos/{Config.GITEA_ORG}/{repo_name}"
        resp = self.session.get(f"{Config.GITEA_API}{endpoint}")
        if resp.status_code == 200:
            print(f"   Deleting existing repo...")
            self.session.delete(f"{Config.GITEA_API}{endpoint}")
            time.sleep(2)
            print(f"   ✅ Deleted")

    def ensure_org(self):
        """ساخت Organization"""
        print(f"\n🏢 Ensuring organization: {Config.GITEA_ORG}")
        resp = self.session.get(f"{Config.GITEA_API}/orgs/{Config.GITEA_ORG}")
        if resp.status_code == 200:
            print(f"   ✅ Exists")
            return True

        result = self._api("POST", "/orgs", json={
            "username": Config.GITEA_ORG,
            "full_name": "Crawled GitHub Projects",
            "description": "Projects crawled from GitHub for training data",
            "visibility": "public",
        })
        if result:
            print(f"   ✅ Created")
            return True
        return False

    def create_empty_repo(self, repo_name, description=""):
        """ساخت ریپوی خالی"""
        print(f"\n📦 Creating repo: {Config.GITEA_ORG}/{repo_name}")
        result = self._api("POST", f"/orgs/{Config.GITEA_ORG}/repos", json={
            "name": repo_name,
            "description": description[:255] if description else "",
            "private": False,
            "auto_init": True,
            "default_branch": "main",
        })
        if result:
            print(f"   ✅ Created")
            time.sleep(2)
            return True
        return False

    def push_files_via_git(self, repo_name, data):
        """Push فایل‌ها با git مستقیم (بدون مشکل SHA)"""
        print(f"\n📁 Pushing files via Git...")

        work_dir = f"_git_temp_{repo_name}"

        # Cleanup
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)

        # Clone
        gitea_user = self._get_current_user()
        if not gitea_user:
            print("   ❌ Cannot get Gitea username")
            return False

        clone_url = f"http://{gitea_user}:{Config.GITEA_TOKEN}@localhost:3000/{Config.GITEA_ORG}/{repo_name}.git"

        print(f"   📥 Cloning repo...")
        result = subprocess.run(
            ["git", "clone", clone_url, work_dir],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"   ❌ Clone failed: {result.stderr}")
            return False

        # Write README
        if data.get("readme"):
            readme_path = os.path.join(work_dir, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(data["readme"])
            print(f"   📄 README.md written")

        # Write source files
        source_files = data.get("source_files", [])
        print(f"   📁 Writing {len(source_files)} source files...")
        for sf in source_files:
            filepath = os.path.join(work_dir, sf["path"])
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(sf["content"])
            except Exception as e:
                print(f"   ⚠️ Skip {sf['path']}: {e}")

        # Write crawled data JSONs
        crawled_dir = os.path.join(work_dir, "_crawled_data")
        os.makedirs(crawled_dir, exist_ok=True)

        if data.get("issues"):
            with open(os.path.join(crawled_dir, "issues.json"), "w", encoding="utf-8") as f:
                json.dump(data["issues"], f, indent=2, ensure_ascii=False)

        if data.get("pull_requests"):
            with open(os.path.join(crawled_dir, "pull_requests.json"), "w", encoding="utf-8") as f:
                json.dump(data["pull_requests"], f, indent=2, ensure_ascii=False)

        if data.get("commits"):
            with open(os.path.join(crawled_dir, "commits.json"), "w", encoding="utf-8") as f:
                json.dump(data["commits"], f, indent=2, ensure_ascii=False)

        if data.get("repo_info"):
            with open(os.path.join(crawled_dir, "repo_info.json"), "w", encoding="utf-8") as f:
                json.dump(data["repo_info"], f, indent=2, ensure_ascii=False)

        # Git add, commit, push
        print(f"   📤 Committing and pushing...")
        cmds = [
            ["git", "add", "-A"],
            ["git", "commit", "-m", "Add crawled source files and data"],
            ["git", "push", "origin", "main"],
        ]

        for cmd in cmds:
            result = subprocess.run(
                cmd, cwd=work_dir, capture_output=True, text=True
            )
            if result.returncode != 0 and "nothing to commit" not in result.stdout + result.stderr:
                print(f"   ⚠️ {' '.join(cmd)}: {result.stderr[:200]}")

        print(f"   ✅ Files pushed successfully!")

        # Cleanup
        shutil.rmtree(work_dir, ignore_errors=True)
        return True

    def _get_current_user(self):
        """دریافت نام کاربر فعلی Gitea"""
        resp = self.session.get(f"{Config.GITEA_API}/user")
        if resp.status_code == 200:
            return resp.json().get("login")
        return None

    def create_issues(self, repo_name, issues):
        """ساخت Issues در Gitea"""
        if not issues:
            return

        print(f"\n🐛 Creating {len(issues)} issues...")
        created = 0
        for i, issue in enumerate(issues):
            body = issue.get("body", "") or ""
            body += f"\n\n---\n"
            body += f"📌 **Original Issue #{issue['number']}**\n"
            body += f"🏷️ Labels: {', '.join(issue.get('labels', []))}\n"
            body += f"📅 Created: {issue.get('created_at', 'N/A')}\n"
            if issue.get("closed_at"):
                body += f"✅ Closed: {issue['closed_at']}\n"

            result = self._api("POST",
                f"/repos/{Config.GITEA_ORG}/{repo_name}/issues",
                json={
                    "title": f"[#{issue['number']}] {issue['title']}",
                    "body": body,
                }
            )

            if result and result.get("id"):
                created += 1
                gitea_id = result.get("number", result.get("id"))

                # Comments
                for comment in issue.get("comments", []):
                    comment_body = f"**@{comment.get('user', 'unknown')}** ({comment.get('created_at', '')}):\n\n"
                    comment_body += comment.get("body", "")
                    self._api("POST",
                        f"/repos/{Config.GITEA_ORG}/{repo_name}/issues/{gitea_id}/comments",
                        json={"body": comment_body}
                    )
                    time.sleep(0.02)

                # Close if needed
                if issue.get("state") == "closed":
                    self._api("PATCH",
                        f"/repos/{Config.GITEA_ORG}/{repo_name}/issues/{gitea_id}",
                        json={"state": "closed"}
                    )

            if (i + 1) % 50 == 0:
                print(f"   ... {i+1}/{len(issues)}")
            time.sleep(0.05)

        print(f"   ✅ Created {created}/{len(issues)} issues")

    def create_prs_as_issues(self, repo_name, prs):
        """ساخت PRs به عنوان Issue"""
        if not prs:
            return

        print(f"\n🔀 Creating {len(prs)} PRs as issues...")
        created = 0
        for i, pr in enumerate(prs):
            body = f"## 🔀 Pull Request #{pr['number']}\n\n"
            body += pr.get("body", "") or ""
            body += f"\n\n---\n"
            body += f"**State:** {'✅ Merged' if pr.get('merged') else pr.get('state', 'unknown')}\n"
            body += f"**Labels:** {', '.join(pr.get('labels', []))}\n"
            body += f"**Created:** {pr.get('created_at', 'N/A')}\n"
            if pr.get("merged_at"):
                body += f"**Merged:** {pr['merged_at']}\n"
            body += f"**Additions:** +{pr.get('additions', 0)} "
            body += f"**Deletions:** -{pr.get('deletions', 0)}\n"

            # Changed files with diffs
            if pr.get("changed_files"):
                body += f"\n### 📁 Changed Files ({len(pr['changed_files'])})\n\n"
                for f in pr["changed_files"]:
                    body += f"#### `{f['filename']}` ({f['status']})\n"
                    if f.get("patch"):
                        body += f"```diff\n{f['patch'][:3000]}\n```\n\n"

            # Review comments
            if pr.get("review_comments"):
                body += f"\n### 💬 Code Review Comments\n\n"
                for r in pr["review_comments"]:
                    body += f"**@{r['user']}** on `{r.get('path', '')}` ({r.get('created_at', '')}):\n"
                    if r.get("diff_hunk"):
                        body += f"```diff\n{r['diff_hunk']}\n```\n"
                    body += f"> {r.get('body', '')}\n\n"

            # Truncate
            if len(body) > 60000:
                body = body[:60000] + "\n\n... (truncated)"

            result = self._api("POST",
                f"/repos/{Config.GITEA_ORG}/{repo_name}/issues",
                json={
                    "title": f"[PR #{pr['number']}] {pr['title']}",
                    "body": body,
                }
            )

            if result and result.get("id"):
                created += 1
                gitea_id = result.get("number", result.get("id"))

                # Comments
                for comment in pr.get("comments", []):
                    comment_body = f"**@{comment.get('user', 'unknown')}** ({comment.get('created_at', '')}):\n\n"
                    comment_body += comment.get("body", "")
                    self._api("POST",
                        f"/repos/{Config.GITEA_ORG}/{repo_name}/issues/{gitea_id}/comments",
                        json={"body": comment_body}
                    )
                    time.sleep(0.02)

                # Close if merged/closed
                if pr.get("state") == "closed" or pr.get("merged"):
                    self._api("PATCH",
                        f"/repos/{Config.GITEA_ORG}/{repo_name}/issues/{gitea_id}",
                        json={"state": "closed"}
                    )

            if (i + 1) % 50 == 0:
                print(f"   ... {i+1}/{len(prs)}")
            time.sleep(0.05)

        print(f"   ✅ Created {created}/{len(prs)} PRs as issues")


def main():
    # Load backup
    backup_file = "crawled_data_backup/fastapi_fastapi.json"

    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        return

    print(f"📂 Loading backup: {backup_file}")
    with open(backup_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"   📁 Source files: {len(data.get('source_files', []))}")
    print(f"   🐛 Issues: {len(data.get('issues', []))}")
    print(f"   🔀 PRs: {len(data.get('pull_requests', []))}")
    print(f"   📝 Commits: {len(data.get('commits', []))}")

    repo_name = "fastapi"
    pusher = GiteaSmartPusher()

    # 1. Organization
    pusher.ensure_org()

    # 2. Delete old repo
    pusher.delete_repo_if_exists(repo_name)

    # 3. Create new repo
    description = data.get("repo_info", {}).get("description", "")
    pusher.create_empty_repo(repo_name, description)

    # 4. Push files via Git (no SHA issues!)
    pusher.push_files_via_git(repo_name, data)

    # 5. Create Issues
    pusher.create_issues(repo_name, data.get("issues", []))

    # 6. Create PRs as Issues
    pusher.create_prs_as_issues(repo_name, data.get("pull_requests", []))

    # Done!
    print(f"\n{'='*60}")
    print(f"✅ ALL DONE!")
    print(f"🔗 {Config.GITEA_URL}/{Config.GITEA_ORG}/{repo_name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()