"""
RAG Engine
ترکیب جستجوی معنایی (ChromaDB) با تولید پاسخ (LLM)
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from config import Config
from llm_client import LLMClient


class RAGEngine:
    def __init__(self):
        print("\n🧠 Initializing RAG Engine...")

        # ─── Embedding Model ───
        print(f"   📦 Loading embedding model: {Config.EMBEDDING_MODEL}")
        self.embedder = SentenceTransformer(Config.EMBEDDING_MODEL)
        print(f"   ✅ Embedding loaded (dim: {self.embedder.get_sentence_embedding_dimension()})")

        # ─── ChromaDB ───
        print(f"   🗄️  Connecting to ChromaDB: {Config.CHROMA_PERSIST_DIR}")
        self.chroma_client = chromadb.PersistentClient(
            path=Config.CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )

        # بارگذاری collections
        self.collections = {}
        collection_map = {
            "code": Config.COLLECTION_CODE,
            "issue": Config.COLLECTION_ISSUES,
            "pull_request": Config.COLLECTION_PRS,
            "commit": Config.COLLECTION_COMMITS,
        }

        for key, name in collection_map.items():
            try:
                col = self.chroma_client.get_collection(name)
                self.collections[key] = col
                print(f"      ✅ {key}: {col.count()} documents")
            except Exception:
                print(f"      ⚠️ {key}: not found")

        # ─── LLM ───
        self.llm = LLMClient()
        self.llm.check_connection()

        print("\n   ✅ RAG Engine ready!")

    # ─── Embedding ───

    def _embed(self, text):
        """تبدیل متن به بردار"""
        embedding = self.embedder.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()[0]

    # ─── Retrieve ───

    def retrieve(self, query, collections=None, top_k=None, score_threshold=None):
        """
        بازیابی اسناد مرتبط

        Args:
            query: سوال کاربر
            collections: لیست collection ها (None = همه)
            top_k: تعداد نتایج
            score_threshold: حداقل score

        Returns:
            list[dict]: نتایج مرتب شده
        """
        if top_k is None:
            top_k = Config.RAG_TOP_K
        if score_threshold is None:
            score_threshold = Config.RAG_SCORE_THRESHOLD

        query_embedding = self._embed(query)

        # اگه collection مشخص نشده → همه
        if collections is None:
            target_collections = list(self.collections.keys())
        else:
            target_collections = collections

        all_results = []

        for col_name in target_collections:
            collection = self.collections.get(col_name)
            if not collection or collection.count() == 0:
                continue

            try:
                n = min(top_k, collection.count())
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n,
                    include=["documents", "metadatas", "distances"],
                )

                if not results or not results.get("documents"):
                    continue

                docs = results["documents"][0]
                metas = results["metadatas"][0]
                dists = results["distances"][0]

                for doc, meta, dist in zip(docs, metas, dists):
                    score = round(1 - dist, 4)
                    if score >= score_threshold:
                        all_results.append({
                            "content": doc,
                            "metadata": meta,
                            "collection": col_name,
                            "score": score,
                        })

            except Exception as e:
                print(f"   ⚠️ Search error in {col_name}: {e}")

        # مرتب‌سازی بر اساس score
        all_results.sort(key=lambda x: x["score"], reverse=True)

        return all_results[:top_k]

    # ─── Context Building ───

    def build_context(self, results):
        """
        ساخت context از نتایج جستجو

        Args:
            results: خروجی retrieve

        Returns:
            str: متن context
        """
        if not results:
            return ""

        context_parts = []
        total_length = 0

        for i, result in enumerate(results, 1):
            meta = result["metadata"]
            collection = result["collection"]
            score = result["score"]

            # هدر
            header = f"[Source {i} | {collection} | relevance: {score}]"

            if collection == "code":
                header += f"\nFile: {meta.get('file_path', 'unknown')}"
                header += f" (Language: {meta.get('language', 'unknown')})"
            elif collection == "issue":
                header += f"\nIssue #{meta.get('issue_number', '?')}: {meta.get('title', '')}"
                header += f" (State: {meta.get('state', 'unknown')})"
            elif collection == "pull_request":
                header += f"\nPR #{meta.get('pr_number', '?')}: {meta.get('title', '')}"
                status = "Merged" if meta.get("merged") else meta.get("state", "unknown")
                header += f" (Status: {status})"
            elif collection == "commit":
                header += f"\nCommit {meta.get('sha', '?')}: {meta.get('message', '')}"

            section = f"{header}\n{result['content']}"

            # چک طول کل
            if total_length + len(section) > Config.RAG_MAX_CONTEXT_LENGTH:
                remaining = Config.RAG_MAX_CONTEXT_LENGTH - total_length - 100
                if remaining > 200:
                    section = section[:remaining] + "\n... (truncated)"
                    context_parts.append(section)
                break

            context_parts.append(section)
            total_length += len(section)

        return "\n\n---\n\n".join(context_parts)

    # ─── Prompt Building ───

    def build_prompt(self, query, context):
        """ساخت prompt نهایی"""
        if context:
            prompt = f"""Based on the following context from the repository, answer the user's question.

## Context:
{context}

## Question:
{query}

## Instructions:
- Use the context above to provide an accurate answer
- Reference specific files, issues, or PRs when relevant
- Provide code examples when appropriate
- If the context doesn't contain enough information, say so

## Answer:"""
        else:
            prompt = f"""Answer the following question about the repository.
Note: No relevant context was found in the repository for this question.

## Question:
{query}

## Answer:"""

        return prompt

    # ─── Build Sources ───

    def _build_sources(self, results):
        """ساخت لیست sources از نتایج"""
        sources = []
        for r in results:
            source = {
                "type": r["collection"],
                "score": r["score"],
            }
            meta = r["metadata"]

            if r["collection"] == "code":
                source["file"] = meta.get("file_path", "")
            elif r["collection"] == "issue":
                source["issue_number"] = meta.get("issue_number", 0)
                source["title"] = meta.get("title", "")
            elif r["collection"] == "pull_request":
                source["pr_number"] = meta.get("pr_number", 0)
                source["title"] = meta.get("title", "")
            elif r["collection"] == "commit":
                source["sha"] = meta.get("sha", "")
                source["message"] = meta.get("message", "")

            sources.append(source)

        return sources

    # ─── Main Query ───

    def query(self, question, collections=None, top_k=None, temperature=0.7):
        """
        سوال از RAG

        Args:
            question: سوال کاربر
            collections: فیلتر collection ها
            top_k: تعداد context
            temperature: خلاقیت LLM

        Returns:
            dict: {answer, sources, context_length, sources_count}
        """
        # ۱. بازیابی
        results = self.retrieve(question, collections=collections, top_k=top_k)

        # ۲. ساخت context
        context = self.build_context(results)

        # ۳. ساخت prompt
        prompt = self.build_prompt(question, context)

        # ۴. تولید پاسخ
        answer = self.llm.generate(prompt, temperature=temperature)

        # ۵. ساخت sources
        sources = self._build_sources(results)

        return {
            "answer": answer,
            "sources": sources,
            "context_length": len(context),
            "sources_count": len(sources),
        }

    def query_stream(self, question, collections=None, top_k=None, temperature=0.7):
        """
        سوال از RAG بصورت streaming

        Yields:
            dict: {type: "sources"|"token"|"done", data: ...}
        """
        # ۱. بازیابی
        results = self.retrieve(question, collections=collections, top_k=top_k)

        # ۲. ارسال sources
        sources = self._build_sources(results)
        yield {"type": "sources", "data": sources}

        # ۳. ساخت context و prompt
        context = self.build_context(results)
        prompt = self.build_prompt(question, context)

        # ۴. Stream tokens
        for token in self.llm.generate_stream(prompt, temperature=temperature):
            yield {"type": "token", "data": token}

        yield {"type": "done", "data": None}

    # ─── Stats ───

    def get_stats(self):
        """آمار RAG Engine"""
        stats = {
            "llm_model": Config.OLLAMA_MODEL,
            "llm_provider": Config.LLM_PROVIDER,
            "embedding_model": Config.EMBEDDING_MODEL,
            "collections": {},
            "total_documents": 0,
        }

        for name, col in self.collections.items():
            count = col.count()
            stats["collections"][name] = count
            stats["total_documents"] += count

        return stats