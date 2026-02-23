"""
QA Dataset Generator
فرمت Alpaca: instruction, input, output

از Issues استخراج میشه: سوال (issue) → جواب (comments/resolution)
"""

import json
import os
import re
import requests
from tqdm import tqdm
from config import Config


class QADatasetGenerator:
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

    def _get_all_issues(self):
        """دریافت تمام Issues (فقط issue ها، نه PRها)"""
        print("\n📥 Fetching all issues from Gitea...")
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
                if not title.startswith("[PR #"):
                    all_issues.append(issue)

            if len(data) < 50:
                break

            page += 1

        print(f"   Found {len(all_issues)} issues (excluding PRs)")
        return all_issues

    def _get_issue_comments(self, issue_number):
        """دریافت کامنت‌های یک Issue"""
        endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/issues/{issue_number}/comments"
        return self._api(endpoint) or []

    def _clean_text(self, text):
        """تمیز کردن متن"""
        if not text:
            return ""
        text = re.sub(r'\n---\n📌.*$', '', text, flags=re.DOTALL)
        return text.strip()

    def _extract_code_blocks(self, text):
        """استخراج بلاک‌های کد"""
        blocks = re.findall(r'```[\w]*\n(.*?)```', text, re.DOTALL)
        return blocks

    def _has_code(self, text):
        """آیا متن شامل کد هست؟"""
        return bool(re.search(r'```', text))

    def generate_question_answer(self):
        """
        تولید سوال-جواب از Issues
        Issue title/body = سوال
        Comments = جواب
        """
        print("\n❓ Generating QA pairs from issues...")

        issues = self._get_all_issues()

        for issue in tqdm(issues, desc="   Processing issues"):
            title = issue.get("title", "")
            body = self._clean_text(issue.get("body", ""))
            issue_number = issue.get("number")
            labels = [l.get("name", "") for l in issue.get("labels", [])]

            if not title or len(title) < 10:
                continue

            comments = self._get_issue_comments(issue_number)
            if not comments:
                continue

            # ساخت سوال
            clean_title = re.sub(r'^\[#\d+\]\s*', '', title).strip()
            question = clean_title
            if body and len(body) > 20:
                question += f"\n\nDetails:\n{body[:2000]}"

            # ساخت جواب از کامنت‌ها
            answer_parts = []
            for comment in comments:
                comment_body = comment.get("body", "")
                if not comment_body or len(comment_body) < 20:
                    continue
                comment_body = re.sub(r'^\*\*@.*?\*\*.*?:\n\n', '', comment_body)
                answer_parts.append(comment_body.strip())

            if not answer_parts:
                continue

            best_answer = answer_parts[0]
            full_answer = "\n\n---\n\n".join(answer_parts[:5])

            # نوع ۱: سوال → بهترین جواب
            self.dataset.append({
                "instruction": question,
                "input": f"Repository: FastAPI\nLabels: {', '.join(labels)}",
                "output": best_answer[:5000],
                "source": "issue",
                "type": "qa_best_answer",
                "issue_number": issue_number,
            })

            # نوع ۲: سوال → جواب کامل
            if len(answer_parts) > 1:
                self.dataset.append({
                    "instruction": f"Provide a comprehensive answer to this question: {clean_title}",
                    "input": body[:2000] if body else "No additional context",
                    "output": full_answer[:8000],
                    "source": "issue",
                    "type": "qa_comprehensive",
                    "issue_number": issue_number,
                })

            # نوع ۳: QA تکنیکال (اگه کد داره)
            if self._has_code(body) or any(self._has_code(a) for a in answer_parts):
                code_blocks_q = self._extract_code_blocks(body)
                code_blocks_a = []
                for a in answer_parts:
                    code_blocks_a.extend(self._extract_code_blocks(a))

                if code_blocks_q or code_blocks_a:
                    self.dataset.append({
                        "instruction": f"Debug and solve this technical issue: {clean_title}",
                        "input": body[:3000] if body else question,
                        "output": best_answer[:5000],
                        "source": "issue",
                        "type": "qa_technical",
                        "issue_number": issue_number,
                    })

    def generate_from_closed_issues(self):
        """
        تولید QA از issue های بسته شده
        """
        print("\n✅ Generating QA from closed/resolved issues...")

        issues = self._get_all_issues()
        closed_issues = [i for i in issues if i.get("state") == "closed"]

        print(f"   Found {len(closed_issues)} closed issues")

        for issue in tqdm(closed_issues, desc="   Closed issues"):
            title = issue.get("title", "")
            body = self._clean_text(issue.get("body", ""))
            issue_number = issue.get("number")

            clean_title = re.sub(r'^\[#\d+\]\s*', '', title).strip()

            comments = self._get_issue_comments(issue_number)

            if not comments:
                continue

            last_comment = comments[-1].get("body", "")
            last_comment = re.sub(r'^\*\*@.*?\*\*.*?:\n\n', '', last_comment)

            if len(last_comment) < 30:
                continue

            self.dataset.append({
                "instruction": f"How was this issue resolved: {clean_title}",
                "input": body[:2000] if body else "No additional context provided",
                "output": f"Resolution:\n{last_comment[:5000]}",
                "source": "issue_closed",
                "type": "qa_resolution",
                "issue_number": issue_number,
            })

    def generate_how_to(self):
        """
        تولید How-to از issues با سوالات how/what/why
        """
        print("\n📖 Generating How-to QA pairs...")

        issues = self._get_all_issues()

        keywords = ["how", "what", "why", "can i", "is it possible",
                     "does", "should", "best way", "example", "help"]

        for issue in tqdm(issues, desc="   How-to issues"):
            title = issue.get("title", "")
            clean_title = re.sub(r'^\[#\d+\]\s*', '', title).strip().lower()
            body = self._clean_text(issue.get("body", ""))
            issue_number = issue.get("number")

            is_question = any(kw in clean_title for kw in keywords)
            if not is_question:
                continue

            comments = self._get_issue_comments(issue_number)
            if not comments:
                continue

            best_comments = []
            for c in comments:
                c_body = c.get("body", "")
                c_body = re.sub(r'^\*\*@.*?\*\*.*?:\n\n', '', c_body)
                if len(c_body) > 30:
                    best_comments.append(c_body)

            if not best_comments:
                continue

            answer = "\n\n".join(best_comments[:3])

            self.dataset.append({
                "instruction": re.sub(r'^\[#\d+\]\s*', '', title).strip(),
                "input": body[:2000] if body else "Context: FastAPI web framework",
                "output": answer[:5000],
                "source": "issue",
                "type": "how_to",
                "issue_number": issue_number,
            })

    def generate(self):
        """تولید کل دیتاست QA"""
        print("=" * 60)
        print("❓ QA DATASET GENERATOR")
        print("=" * 60)

        self.generate_question_answer()
        self.generate_from_closed_issues()
        self.generate_how_to()

        # حذف تکراری‌ها
        seen = set()
        unique_dataset = []
        for item in self.dataset:
            key = item["instruction"][:100]
            if key not in seen:
                seen.add(key)
                unique_dataset.append(item)
        self.dataset = unique_dataset

        # ذخیره به فرمت JSONL
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(Config.OUTPUT_DIR, "qa_dataset.jsonl")

        with open(output_path, "w", encoding="utf-8") as f:
            for item in self.dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"\n✅ QA Dataset Generated!")
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