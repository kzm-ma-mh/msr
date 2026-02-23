"""
موتور جستجوی معنایی
"""

from chroma_manager import ChromaManager


class SearchEngine:
    def __init__(self):
        self.chroma = ChromaManager()

    def search(self, query, collection="all", n_results=5, where=None):
        """
        جستجوی معنایی

        Args:
            query: متن جستجو
            collection: "all" | "code" | "issue" | "pull_request" | "commit"
            n_results: تعداد نتایج
            where: فیلتر metadata (dict)

        Returns:
            list[dict]: نتایج مرتب شده بر اساس score
        """
        return self.chroma.search(
            collection_name=collection,
            query=query,
            n_results=n_results,
            where=where,
        )

    def search_code(self, query, n_results=5, language=None):
        """جستجو در سورس کد"""
        where = {"language": language} if language else None
        return self.search(query, "code", n_results, where)

    def search_issues(self, query, n_results=5, state=None):
        """جستجو در Issues"""
        where = {"state": state} if state else None
        return self.search(query, "issue", n_results, where)

    def search_prs(self, query, n_results=5, merged=None):
        """جستجو در Pull Requests"""
        where = {"merged": merged} if merged is not None else None
        return self.search(query, "pull_request", n_results, where)

    def search_commits(self, query, n_results=5):
        """جستجو در Commits"""
        return self.search(query, "commit", n_results)

    def get_context_for_rag(self, query, n_results=10):
        """
        دریافت context برای RAG
        از همه collections جستجو میکنه و بهترین نتایج رو برمیگردونه

        Args:
            query: سوال کاربر
            n_results: تعداد نتایج

        Returns:
            str: متن context آماده برای ارسال به LLM
        """
        results = self.search(query, collection="all", n_results=n_results)

        if not results:
            return "No relevant context found."

        context_parts = []
        for i, result in enumerate(results, 1):
            meta = result["metadata"]
            score = result["score"]
            collection = result["collection"]

            header = f"--- Source {i} ({collection}, score: {score}) ---"

            # اضافه کردن metadata مرتبط
            if collection == "code":
                header += f"\nFile: {meta.get('file_path', '')}"
            elif collection == "issue":
                header += f"\nIssue #{meta.get('issue_number', '')}: {meta.get('title', '')}"
            elif collection == "pull_request":
                header += f"\nPR #{meta.get('pr_number', '')}: {meta.get('title', '')}"
            elif collection == "commit":
                header += f"\nCommit {meta.get('sha', '')}: {meta.get('message', '')}"

            context_parts.append(f"{header}\n{result['content']}")

        return "\n\n".join(context_parts)

    def format_result(self, result, index=1):
        """فرمت نمایشی یک نتیجه"""
        meta = result["metadata"]
        score = result["score"]
        collection = result["collection"]
        content = result["content"]

        output = f"\n━━━ Result {index} (score: {score:.3f}) ━━━\n"
        output += f"📁 Type: {collection}\n"

        if collection == "code":
            output += f"📄 File: {meta.get('file_path', 'N/A')}\n"
            output += f"🔤 Language: {meta.get('language', 'N/A')}\n"
        elif collection == "issue":
            output += f"🐛 Issue #{meta.get('issue_number', '')}\n"
            output += f"📌 Title: {meta.get('title', '')}\n"
            output += f"📊 State: {meta.get('state', '')}\n"
        elif collection == "pull_request":
            output += f"🔀 PR #{meta.get('pr_number', '')}\n"
            output += f"📌 Title: {meta.get('title', '')}\n"
            output += f"📊 Merged: {meta.get('merged', False)}\n"
        elif collection == "commit":
            output += f"📝 SHA: {meta.get('sha', '')}\n"
            output += f"👤 Author: {meta.get('author', '')}\n"
            output += f"💬 Message: {meta.get('message', '')}\n"

        # محتوا (حداکثر ۳۰۰ کاراکتر)
        preview = content[:300] + "..." if len(content) > 300 else content
        output += f"\n{preview}\n"

        return output