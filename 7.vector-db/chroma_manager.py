"""
مدیریت ChromaDB
هر نوع داده (code, issue, pr, commit) collection جداگانه داره
"""

import chromadb
from chromadb.config import Settings
from config import Config
from embedding_manager import EmbeddingManager


class ChromaManager:
    def __init__(self):
        print(f"\n🗄️  Initializing ChromaDB...")
        print(f"   Path: {Config.CHROMA_PERSIST_DIR}")

        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self.embedder = EmbeddingManager()

        # ساخت collections
        self.collections = {
            "code": self._get_or_create(Config.COLLECTION_CODE),
            "issue": self._get_or_create(Config.COLLECTION_ISSUES),
            "pull_request": self._get_or_create(Config.COLLECTION_PRS),
            "commit": self._get_or_create(Config.COLLECTION_COMMITS),
        }

        print(f"   ✅ Collections ready:")
        for name, col in self.collections.items():
            print(f"      {name}: {col.count()} documents")

    def _get_or_create(self, name):
        """ساخت یا دریافت collection"""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ─── CRUD Operations ───

    def add(self, collection_name, documents, metadatas, ids):
        """
        اضافه کردن اسناد

        Args:
            collection_name: "code" | "issue" | "pull_request" | "commit"
            documents: لیست متن‌ها
            metadatas: لیست metadata
            ids: لیست ID (unique)
        """
        if not documents:
            return 0

        collection = self.collections.get(collection_name)
        if not collection:
            print(f"   ❌ Unknown collection: {collection_name}")
            return 0

        # تولید embeddings
        embeddings = self.embedder.embed_batch(documents)

        # اضافه در batch
        batch_size = 100
        added = 0
        for i in range(0, len(documents), batch_size):
            end = min(i + batch_size, len(documents))
            try:
                collection.upsert(
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end],
                )
                added += end - i
            except Exception as e:
                print(f"   ❌ Error adding batch {i}-{end}: {e}")

        return added

    def search(self, collection_name, query, n_results=5, where=None):
        """
        جستجوی معنایی

        Args:
            collection_name: نام collection یا "all"
            query: متن جستجو
            n_results: تعداد نتایج
            where: فیلتر metadata

        Returns:
            list[dict]: لیست نتایج
        """
        query_embedding = self.embedder.embed_single(query)

        results = []

        if collection_name == "all":
            # جستجو در همه collections
            for col_name, collection in self.collections.items():
                if collection.count() == 0:
                    continue
                try:
                    col_results = collection.query(
                        query_embeddings=[query_embedding],
                        n_results=min(n_results, collection.count()),
                        where=where,
                        include=["documents", "metadatas", "distances"],
                    )
                    results.extend(self._format_results(col_results, col_name))
                except Exception as e:
                    print(f"   ⚠️ Search error in {col_name}: {e}")
        else:
            collection = self.collections.get(collection_name)
            if not collection or collection.count() == 0:
                return []

            try:
                col_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(n_results, collection.count()),
                    where=where,
                    include=["documents", "metadatas", "distances"],
                )
                results = self._format_results(col_results, collection_name)
            except Exception as e:
                print(f"   ⚠️ Search error: {e}")

        # مرتب‌سازی بر اساس score (بالاترین اول)
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:n_results]

    def _format_results(self, raw_results, collection_name):
        """فرمت‌دهی نتایج خام ChromaDB"""
        formatted = []

        if not raw_results or not raw_results.get("documents"):
            return formatted

        docs = raw_results["documents"][0]
        metas = raw_results["metadatas"][0]
        distances = raw_results["distances"][0]

        for doc, meta, dist in zip(docs, metas, distances):
            formatted.append({
                "content": doc,
                "metadata": meta,
                "collection": collection_name,
                "score": round(1 - dist, 4),  # cosine distance → similarity
                "distance": round(dist, 4),
            })

        return formatted

    # ─── Statistics ───

    def get_stats(self):
        """آمار کامل"""
        stats = {"total": 0, "collections": {}}

        for name, collection in self.collections.items():
            count = collection.count()
            stats["collections"][name] = count
            stats["total"] += count

        return stats

    # ─── Management ───

    def clear_collection(self, collection_name):
        """پاک کردن یک collection"""
        if collection_name in self.collections:
            col = self.collections[collection_name]
            self.client.delete_collection(col.name)
            # بازسازی
            config_map = {
                "code": Config.COLLECTION_CODE,
                "issue": Config.COLLECTION_ISSUES,
                "pull_request": Config.COLLECTION_PRS,
                "commit": Config.COLLECTION_COMMITS,
            }
            self.collections[collection_name] = self._get_or_create(
                config_map[collection_name]
            )
            print(f"   🗑️  Cleared: {collection_name}")

    def clear_all(self):
        """پاک کردن همه collections"""
        for name in list(self.collections.keys()):
            self.clear_collection(name)
        print("   🗑️  All collections cleared")