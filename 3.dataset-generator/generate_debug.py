"""
Debug Dataset Generator
فرمت Alpaca: instruction, input, output

از Pull Requests + Bug Issues استخراج میشه
"""

import json
import os
import re
import requests
from tqdm import tqdm
from config import Config


class DebugDatasetGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.GITEA_HEADERS)
        self.dataset = []

    def _api(self, endpoint, params=None):
        """درخواست به Gitea API"""
        url = f"{Config.GITEA_API}{endpoint}"
        resp = self.session.get(url, params=params)
        if resp.status_code == 200:
            return resp.json()
        return None

    def _get_all_pr_issues(self):
        """دریافت تمام PRها (که به عنوان issue ذخیره شدن)"""
        print("\n📥 Fetching all PRs from Gitea...")
        all_prs = []
        page = 1

        while True:
            endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/issues"
            params = {
                "type": "issues",
                "state": "all",
                "limit": 50,
                "page": page,
            }
            data = self._api(endpoint, params)

            if not data:
                break

            for issue in data:
                title = issue.get("title", "")
                if title.startswith("[PR #"):
                    all_prs.append(issue)

            if len(data) < 50:
                break

            page += 1

        print(f"   Found {len(all_prs)} PRs")
        return all_prs

    def _get_bug_issues(self):
        """دریافت Issues مربوط به باگ"""
        print("\n📥 Fetching bug issues from Gitea...")
        all_issues = []
        page = 1

        while True:
            endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/issues"
            params = {
                "type": "issues",
                "state": "all",
                "limit": 50,
                "page": page,
            }
            data = self._api(endpoint, params)

            if not data:
                break

            for issue in data:
                title = issue.get("title", "")
                body = issue.get("body", "") or ""

                if title.startswith("[PR #"):
                    continue

                bug_keywords = ["bug", "error", "fix", "crash", "fail",
                                "broken", "issue", "exception", "traceback",
                                "typeerror", "valueerror", "attributeerror",
                                "keyerror", "importerror", "runtimeerror"]

                text = (title + " " + body).lower()
                if any(kw in text for kw in bug_keywords):
                    all_issues.append(issue)

            if len(data) < 50:
                break

            page += 1

        print(f"   Found {len(all_issues)} bug-related issues")
        return all_issues

    def _get_issue_comments(self, issue_number):
        """دریافت کامنت‌های یک Issue"""
        endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/issues/{issue_number}/comments"
        return self._api(endpoint) or []

    def _extract_diff_blocks(self, text):
        """استخراج بلاک‌های diff از متن"""
        diffs = re.findall(r'```diff\n(.*?)```', text, re.DOTALL)
        return diffs

    def _extract_code_blocks(self, text):
        """استخراج بلاک‌های کد از متن"""
        blocks = re.findall(r'```[\w]*\n(.*?)```', text, re.DOTALL)
        return blocks

    def _extract_changed_files_from_body(self, body):
        """استخراج فایل‌های تغییر یافته از body PR"""
        files = re.findall(r'#### `(.+?)` \((\w+)\)', body)
        diffs = re.findall(r'#### `(.+?)` \(\w+\)\n```diff\n(.*?)```', body, re.DOTALL)
        return files, diffs

    def _extract_review_comments(self, body):
        """استخراج review comments از body PR"""
        reviews = []
        pattern = r'\*\*@(\w+)\*\* on `(.+?)` \(.*?\):\n(?:```diff\n(.*?)```\n)?> (.*?)(?:\n\n|$)'
        matches = re.findall(pattern, body, re.DOTALL)
        for match in matches:
            reviews.append({
                "user": match[0],
                "file": match[1],
                "diff": match[2],
                "comment": match[3],
            })
        return reviews

    def _extract_pr_description(self, body):
        """استخراج توضیحات PR (بدون diff)"""
        parts = body.split("### 📁 Changed Files")
        if parts:
            desc = parts[0]
            desc = re.sub(r'## 🔀 Pull Request #\d+\n', '', desc)
            desc = re.sub(r'\n---\n\*\*State:.*$', '', desc, flags=re.DOTALL)
            return desc.strip()[:3000]
        return body[:1000]

    def _build_review_output(self, body, title):
        """ساخت خروجی review"""
        reviews = self._extract_review_comments(body)
        if reviews:
            output = f"Code Review for: {title}\n\n"
            for r in reviews[:5]:
                output += f"📝 **{r['file']}**: {r['comment']}\n\n"
            return output[:5000]
        return f"Changes look good. This PR implements: {title}"

    def generate_from_prs(self):
        """
        تولید Debug dataset از Pull Requests
        PR title/description = مشکل
        Diff = راه حل
        """
        print("\n🔀 Generating debug data from PRs...")

        prs = self._get_all_pr_issues()

        for pr in tqdm(prs, desc="   Processing PRs"):
            title = pr.get("title", "")
            body = pr.get("body", "") or ""
            pr_number = pr.get("number")

            clean_title = re.sub(r'^\[PR #\d+\]\s*', '', title).strip()

            files, diffs = self._extract_changed_files_from_body(body)
            diff_blocks = self._extract_diff_blocks(body)

            if not diff_blocks:
                continue

            diff_text = "\n\n".join([f"```diff\n{d}\n```" for d in diff_blocks[:5]])

            if len(diff_text) > 8000:
                diff_text = diff_text[:8000] + "\n... (truncated)"

            # نوع ۱: Fix/Bug PR → Debug
            fix_keywords = ["fix", "bug", "patch", "resolve", "correct",
                            "repair", "handle", "error", "crash"]

            if any(kw in clean_title.lower() for kw in fix_keywords):
                self.dataset.append({
                    "instruction": f"Fix the following bug: {clean_title}",
                    "input": self._extract_pr_description(body),
                    "output": diff_text,
                    "source": "pr_bugfix",
                    "type": "bug_fix",
                    "pr_number": pr_number,
                })

                self.dataset.append({
                    "instruction": "Explain what bug this code change fixes and why",
                    "input": diff_text[:4000],
                    "output": f"Bug: {clean_title}\n\n{self._extract_pr_description(body)}",
                    "source": "pr_bugfix",
                    "type": "bug_explanation",
                    "pr_number": pr_number,
                })

            # نوع ۲: هر PR → Code Review
            self.dataset.append({
                "instruction": f"Review the following code changes: {clean_title}",
                "input": diff_text[:5000],
                "output": self._build_review_output(body, clean_title),
                "source": "pr",
                "type": "code_review",
                "pr_number": pr_number,
            })

            # نوع ۳: از review comments
            reviews = self._extract_review_comments(body)
            for review in reviews:
                if review["comment"] and len(review["comment"]) > 20:
                    self.dataset.append({
                        "instruction": f"Review this code change in `{review['file']}`",
                        "input": f"```diff\n{review['diff']}\n```" if review["diff"] else f"File: {review['file']}",
                        "output": review["comment"],
                        "source": "pr_review",
                        "type": "inline_review",
                        "pr_number": pr_number,
                    })

    def generate_from_bug_issues(self):
        """
        تولید Debug dataset از Bug Issues
        """
        print("\n🐛 Generating debug data from bug issues...")

        bug_issues = self._get_bug_issues()

        for issue in tqdm(bug_issues, desc="   Bug issues"):
            title = issue.get("title", "")
            body = issue.get("body", "") or ""
            issue_number = issue.get("number")

            clean_title = re.sub(r'^\[#\d+\]\s*', '', title).strip()
            clean_body = re.sub(r'\n---\n📌.*$', '', body, flags=re.DOTALL).strip()

            if len(clean_body) < 30:
                continue

            comments = self._get_issue_comments(issue_number)

            error_blocks = self._extract_code_blocks(clean_body)
            has_traceback = any("traceback" in b.lower() or "error" in b.lower()
                                for b in error_blocks)

            # نوع ۱: Error → Debug
            if error_blocks:
                error_text = "\n\n".join([f"```\n{e}\n```" for e in error_blocks[:3]])

                answer_parts = []
                for c in comments:
                    c_body = c.get("body", "")
                    c_body = re.sub(r'^\*\*@.*?\*\*.*?:\n\n', '', c_body)
                    if len(c_body) > 20:
                        answer_parts.append(c_body)

                if answer_parts:
                    self.dataset.append({
                        "instruction": f"Debug this error: {clean_title}",
                        "input": error_text[:4000],
                        "output": "\n\n".join(answer_parts[:3])[:5000],
                        "source": "bug_issue",
                        "type": "error_debug",
                        "issue_number": issue_number,
                    })

            # نوع ۲: Bug report → Solution
            if comments and issue.get("state") == "closed":
                solution_parts = []
                for c in comments:
                    c_body = c.get("body", "")
                    c_body = re.sub(r'^\*\*@.*?\*\*.*?:\n\n', '', c_body)
                    if len(c_body) > 20:
                        solution_parts.append(c_body)

                if solution_parts:
                    self.dataset.append({
                        "instruction": f"How to fix: {clean_title}",
                        "input": clean_body[:3000],
                        "output": "\n\n".join(solution_parts[:3])[:5000],
                        "source": "bug_issue",
                        "type": "bug_solution",
                        "issue_number": issue_number,
                    })

            # نوع ۳: Traceback → Fix
            if has_traceback and comments:
                self.dataset.append({
                    "instruction": "Analyze this error traceback and suggest a fix",
                    "input": clean_body[:4000],
                    "output": comments[0].get("body", "")[:5000] if comments else "No solution provided yet",
                    "source": "bug_issue",
                    "type": "traceback_analysis",
                    "issue_number": issue_number,
                })

    def generate(self):
        """تولید کل دیتاست Debug"""
        print("=" * 60)
        print("🐛 DEBUG DATASET GENERATOR")
        print("=" * 60)

        self.generate_from_prs()
        self.generate_from_bug_issues()

        # حذف تکراری‌ها
        seen = set()
        unique_dataset = []
        for item in self.dataset:
            key = item["instruction"][:100] + item.get("input", "")[:50]
            if key not in seen:
                seen.add(key)
                unique_dataset.append(item)
        self.dataset = unique_dataset

        # ذخیره به فرمت JSONL
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(Config.OUTPUT_DIR, "debug_dataset.jsonl")

        with open(output_path, "w", encoding="utf-8") as f:
            for item in self.dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"\n✅ Debug Dataset Generated!")
        print(f"   📊 Total samples: {len(self.dataset)}")
        print(f"   💾 Saved to: {output_path}")

        types = {}
        for item in self.dataset:
            t = item.get("type", "unknown")
            types[t] = types.get(t, 0) + 1

        print(f"\n   📈 Breakdown:")
        for t, count in sorted(types.items(), key=lambda x: -x[1]):
            print(f"      {t}: {count}")

        return self.dataset