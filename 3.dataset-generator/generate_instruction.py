"""
Instruction Dataset Generator
فرمت Alpaca: instruction, input, output

از سورس کد + commits + README استخراج میشه
"""

import json
import os
import base64
import requests
from tqdm import tqdm
from config import Config


class InstructionDatasetGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Config.GITEA_HEADERS)
        self.dataset = []

    def _api(self, endpoint):
        """درخواست به Gitea API"""
        url = f"{Config.GITEA_API}{endpoint}"
        resp = self.session.get(url)
        if resp.status_code == 200:
            return resp.json()
        return None

    def _get_file_content(self, path):
        """دریافت محتوای فایل از Gitea"""
        endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/contents/{path}"
        data = self._api(endpoint)
        if data and data.get("content"):
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except Exception:
                return None
        return None

    def _get_all_files(self, path=""):
        """دریافت لیست تمام فایل‌ها بصورت بازگشتی"""
        endpoint = f"/repos/{Config.GITEA_ORG}/{Config.REPO_NAME}/contents/{path}"
        data = self._api(endpoint)
        if not data:
            return []

        files = []
        if isinstance(data, list):
            for item in data:
                if item["type"] == "file":
                    files.append(item["path"])
                elif item["type"] == "dir" and not item["name"].startswith("."):
                    files.extend(self._get_all_files(item["path"]))
        return files

    def generate_from_source_code(self):
        """
        تولید instruction از سورس کد
        مثال: "یک تابع بنویس که..." → کد
        """
        print("\n📝 Generating instructions from source code...")

        all_files = self._get_all_files()
        py_files = [f for f in all_files if f.endswith(".py") and not f.startswith("_crawled_data")]

        print(f"   Found {len(py_files)} Python files")

        for filepath in tqdm(py_files, desc="   Source files"):
            content = self._get_file_content(filepath)
            if not content or len(content) < 50:
                continue

            self._extract_functions(content, filepath)
            self._extract_classes(content, filepath)

    def _extract_functions(self, content, filepath):
        """استخراج توابع و ساخت instruction"""
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("def ") or stripped.startswith("async def "):
                func_name = stripped.split("(")[0].replace("def ", "").replace("async ", "").strip()

                docstring = ""
                func_lines = [line]
                j = i + 1
                indent_level = len(line) - len(line.lstrip())

                while j < len(lines):
                    next_line = lines[j]
                    next_stripped = next_line.strip()

                    if next_stripped == "" and j == i + 1:
                        j += 1
                        continue

                    if next_line.strip() and (len(next_line) - len(next_line.lstrip())) <= indent_level and j > i + 1:
                        break

                    func_lines.append(next_line)

                    if '"""' in next_stripped or "'''" in next_stripped:
                        if docstring == "":
                            docstring = next_stripped.strip("\"'").strip()

                    j += 1

                func_body = "\n".join(func_lines)

                if len(func_body) < 50 or len(func_body) > 5000:
                    i = j
                    continue

                if docstring:
                    instruction = f"Write a Python function named `{func_name}` that {docstring}"
                else:
                    instruction = f"Write a Python function named `{func_name}` based on the following context from `{filepath}`"

                self.dataset.append({
                    "instruction": instruction,
                    "input": f"File: {filepath}",
                    "output": func_body.strip(),
                    "source": "source_code",
                    "type": "function_generation",
                })

                i = j
                continue

            i += 1

    def _extract_classes(self, content, filepath):
        """استخراج کلاس‌ها و ساخت instruction"""
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("class "):
                class_name = stripped.split("(")[0].split(":")[0].replace("class ", "").strip()

                class_lines = [line]
                j = i + 1
                indent_level = len(line) - len(line.lstrip())

                while j < len(lines):
                    next_line = lines[j]
                    if next_line.strip() and (len(next_line) - len(next_line.lstrip())) <= indent_level and j > i + 1:
                        break
                    class_lines.append(next_line)
                    j += 1

                class_body = "\n".join(class_lines)

                if len(class_body) < 100 or len(class_body) > 8000:
                    i = j
                    continue

                self.dataset.append({
                    "instruction": f"Write a Python class named `{class_name}` as implemented in `{filepath}`",
                    "input": f"File: {filepath}\nContext: Part of the FastAPI framework",
                    "output": class_body.strip(),
                    "source": "source_code",
                    "type": "class_generation",
                })

                i = j
                continue

            i += 1

    def generate_from_commits(self):
        """
        تولید instruction از commit messages
        مثال: "این تغییرات رو اعمال کن" → diff
        """
        print("\n📝 Generating instructions from commits...")

        commits_content = self._get_file_content("_crawled_data/commits.json")
        if not commits_content:
            print("   ⚠️ No commits data found")
            return

        commits = json.loads(commits_content)
        print(f"   Found {len(commits)} commits")

        for commit in tqdm(commits, desc="   Commits"):
            message = commit.get("message", "").strip()
            files = commit.get("files", [])

            if not message or not files:
                continue

            patches = []
            for f in files:
                if f.get("patch") and len(f["patch"]) > 20:
                    patches.append(f"### {f['filename']} ({f['status']})\n```diff\n{f['patch']}\n```")

            if not patches:
                continue

            diff_text = "\n\n".join(patches)

            if len(diff_text) > 8000:
                diff_text = diff_text[:8000] + "\n... (truncated)"

            # نوع ۱: از commit message به diff
            self.dataset.append({
                "instruction": f"Implement the following change: {message.split(chr(10))[0]}",
                "input": f"Commit message: {message}",
                "output": diff_text,
                "source": "commit",
                "type": "code_change",
            })

            # نوع ۲: از diff به commit message
            self.dataset.append({
                "instruction": "Write a descriptive commit message for the following code changes",
                "input": diff_text[:4000],
                "output": message,
                "source": "commit",
                "type": "commit_message",
            })

    def generate_from_readme(self):
        """
        تولید instruction از README
        مثال: "این پروژه رو توضیح بده" → توضیحات
        """
        print("\n📝 Generating instructions from README...")

        readme = self._get_file_content("README.md")
        if not readme:
            print("   ⚠️ No README found")
            return

        sections = []
        current_section = {"title": "Introduction", "content": ""}

        for line in readme.split("\n"):
            if line.startswith("## ") or line.startswith("# "):
                if current_section["content"].strip():
                    sections.append(current_section)
                current_section = {
                    "title": line.strip("# ").strip(),
                    "content": "",
                }
            else:
                current_section["content"] += line + "\n"

        if current_section["content"].strip():
            sections.append(current_section)

        print(f"   Found {len(sections)} README sections")

        for section in sections:
            if len(section["content"].strip()) < 50:
                continue

            self.dataset.append({
                "instruction": f"Explain the '{section['title']}' section of the FastAPI documentation",
                "input": f"Section: {section['title']}",
                "output": section["content"].strip(),
                "source": "readme",
                "type": "documentation",
            })

        if len(readme) > 200:
            self.dataset.append({
                "instruction": "Write a comprehensive README for the FastAPI project",
                "input": "Project: FastAPI - A modern, fast web framework for building APIs with Python",
                "output": readme[:10000],
                "source": "readme",
                "type": "readme_generation",
            })

    def generate(self):
        """تولید کل دیتاست Instruction"""
        print("=" * 60)
        print("📚 INSTRUCTION DATASET GENERATOR")
        print("=" * 60)

        self.generate_from_source_code()
        self.generate_from_commits()
        self.generate_from_readme()

        # ذخیره به فرمت JSONL
        os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(Config.OUTPUT_DIR, "instruction_dataset.jsonl")

        with open(output_path, "w", encoding="utf-8") as f:
            for item in self.dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"\n✅ Instruction Dataset Generated!")
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