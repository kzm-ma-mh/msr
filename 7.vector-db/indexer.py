"""
ایندکس کردن داده‌ها در ChromaDB
هر نوع داده پردازش و chunk مخصوص خودش رو داره
"""

import hashlib
from tqdm import tqdm
from config import Config
from data_loader import GiteaDataLoader
from text_splitter import TextSplitter
from chroma_manager import ChromaManager


class Indexer:
    def __init__(self):
        self.loader = GiteaDataLoader()
        self.splitter = TextSplitter()
        self.chroma = ChromaManager()

    def _make_id(self, *parts):
        """ساخت ID یکتا از ترکیب parts"""
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ─── Index Source Code ───

    def index_code(self):
        """ایندکس فایل‌های سورس کد"""
        source_files = self.loader.load_source_files()
        if not source_files:
            return 0

        documents = []
        metadatas = []
        ids = []

        print(f"\n   ✂️  Chunking {len(source_files)} files...")

        for sf in tqdm(source_files, desc="   Chunking code"):
            path = sf["path"]
            content = sf["content"]
            language = sf["language"]

            # انتخاب نوع chunk
            if language == "py":
                chunks = self.splitter.split_code(content, language="python")
            elif language in ("md", "rst", "txt"):
                chunks = self.splitter.split_markdown(content)
            else:
                chunks = self.splitter.split_text(content)

            for i, chunk in enumerate(chunks):
                doc_id = self._make_id("code", Config.REPO_NAME, path, i)

                documents.append(chunk)
                metadatas.append({
                    "repo": Config.REPO_NAME,
                    "file_path": path,
                    "language": language,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })
                ids.append(doc_id)

        added = self.chroma.add("code", documents, metadatas, ids)
        print(f"   ✅ Indexed {added} code chunks")
        return added

    # ─── Index Issues ───

    def index_issues(self):
        """ایندکس Issues"""
        issues = self.loader.load_issues()
        if not issues:
            return 0

        documents = []
        metadatas = []
        ids = []

        print(f"\n   ✂️  Chunking {len(issues)} issues...")

        for issue in tqdm(issues, desc="   Chunking issues"):
            number = issue.get("number", 0)
            title = issue.get("title", "")
            body = issue.get("body", "") or ""
            state = issue.get("state", "unknown")
            labels = issue.get("labels", [])
            comments = issue.get("comments", [])

            # ساخت متن کامل
            full_text = f"Issue #{number}: {title}\n\n{body}"

            if comments:
                full_text += "\n\n--- Comments ---\n"
                for c in comments[:15]:
                    user = c.get("user", "unknown")
                    c_body = c.get("body", "")
                    full_text += f"\n@{user}: {c_body}\n"

            # chunk
            chunks = self.splitter.split_markdown(full_text)

            for i, chunk in enumerate(chunks):
                doc_id = self._make_id("issue", Config.REPO_NAME, number, i)

                documents.append(chunk)
                metadatas.append({
                    "repo": Config.REPO_NAME,
                    "issue_number": number,
                    "title": title[:200],
                    "state": state,
                    "labels": ",".join(labels) if labels else "",
                    "has_comments": len(comments) > 0,
                    "comment_count": len(comments),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })
                ids.append(doc_id)

        added = self.chroma.add("issue", documents, metadatas, ids)
        print(f"   ✅ Indexed {added} issue chunks")
        return added

    # ─── Index Pull Requests ───

    def index_pull_requests(self):
        """ایندکس Pull Requests"""
        prs = self.loader.load_pull_requests()
        if not prs:
            return 0

        documents = []
        metadatas = []
        ids = []

        print(f"\n   ✂️  Chunking {len(prs)} pull requests...")

        for pr in tqdm(prs, desc="   Chunking PRs"):
            number = pr.get("number", 0)
            title = pr.get("title", "")
            body = pr.get("body", "") or ""
            state = pr.get("state", "unknown")
            merged = pr.get("merged", False)
            labels = pr.get("labels", [])
            changed_files = pr.get("changed_files", [])
            review_comments = pr.get("review_comments", [])

            # ساخت متن کامل
            status = "Merged" if merged else state
            full_text = f"PR #{number}: {title}\nStatus: {status}\n\n{body}"

            # تغییرات فایل‌ها
            if changed_files:
                full_text += "\n\n--- Changed Files ---\n"
                for cf in changed_files[:15]:
                    fname = cf.get("filename", "")
                    patch = cf.get("patch", "")
                    if patch:
                        full_text += f"\nFile: {fname}\n```diff\n{patch[:1500]}\n```\n"
                    else:
                        full_text += f"\nFile: {fname} ({cf.get('status', '')})\n"

            # Review comments
            if review_comments:
                full_text += "\n\n--- Reviews ---\n"
                for rc in review_comments[:10]:
                    user = rc.get("user", "unknown")
                    path = rc.get("path", "")
                    rc_body = rc.get("body", "")
                    full_text += f"\n@{user} on {path}: {rc_body}\n"

            # chunk
            chunks = self.splitter.split_markdown(full_text)

            for i, chunk in enumerate(chunks):
                doc_id = self._make_id("pr", Config.REPO_NAME, number, i)

                documents.append(chunk)
                metadatas.append({
                    "repo": Config.REPO_NAME,
                    "pr_number": number,
                    "title": title[:200],
                    "state": state,
                    "merged": merged,
                    "labels": ",".join(labels) if labels else "",
                    "files_changed": len(changed_files),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })
                ids.append(doc_id)

        added = self.chroma.add("pull_request", documents, metadatas, ids)
        print(f"   ✅ Indexed {added} PR chunks")
        return added

    # ─── Index Commits ───

    def index_commits(self):
        """ایندکس Commits"""
        commits = self.loader.load_commits()
        if not commits:
            return 0

        documents = []
        metadatas = []
        ids = []

        print(f"\n   ✂️  Chunking {len(commits)} commits...")

        for commit in tqdm(commits, desc="   Chunking commits"):
            sha = commit.get("sha", "")
            message = commit.get("message", "")
            author = commit.get("author", "unknown")
            date = commit.get("date", "")
            files = commit.get("files", [])

            # ساخت متن کامل
            full_text = f"Commit {sha}\nAuthor: {author}\nDate: {date}\n\n{message}"

            if files:
                full_text += "\n\n--- Changes ---\n"
                for f in files[:15]:
                    fname = f.get("filename", "")
                    patch = f.get("patch", "")
                    if patch:
                        full_text += f"\nFile: {fname}\n```diff\n{patch[:1000]}\n```\n"
                    else:
                        full_text += f"\nFile: {fname} ({f.get('status', '')})\n"

            # chunk
            chunks = self.splitter.split_text(full_text)

            for i, chunk in enumerate(chunks):
                doc_id = self._make_id("commit", Config.REPO_NAME, sha, i)

                documents.append(chunk)
                metadatas.append({
                    "repo": Config.REPO_NAME,
                    "sha": sha,
                    "author": author,
                    "message": message[:200],
                    "files_changed": len(files),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })
                ids.append(doc_id)

        added = self.chroma.add("commit", documents, metadatas, ids)
        print(f"   ✅ Indexed {added} commit chunks")
        return added

    # ─── Index All ───

    def index_all(self, clear=False):
        """ایندکس همه داده‌ها"""
        print("=" * 60)
        print(f"🚀 INDEXING: {Config.GITEA_ORG}/{Config.REPO_NAME}")
        print("=" * 60)

        if clear:
            print("\n🗑️  Clearing existing data...")
            self.chroma.clear_all()

        totals = {}
        totals["code"] = self.index_code()
        totals["issues"] = self.index_issues()
        totals["pull_requests"] = self.index_pull_requests()
        totals["commits"] = self.index_commits()

        # Summary
        print("\n" + "=" * 60)
        print("📊 INDEXING SUMMARY")
        print("=" * 60)

        grand_total = 0
        for name, count in totals.items():
            print(f"   {name}: {count} chunks")
            grand_total += count

        print(f"\n   🏆 Total: {grand_total} chunks indexed")
        print(f"   💾 ChromaDB: {Config.CHROMA_PERSIST_DIR}")

        return totals