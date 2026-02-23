"""
مدیریت Embedding Model (Singleton Pattern)
"""

from sentence_transformers import SentenceTransformer
from config import Config


class EmbeddingManager:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if EmbeddingManager._model is None:
            print(f"📦 Loading embedding model: {Config.EMBEDDING_MODEL}")
            EmbeddingManager._model = SentenceTransformer(Config.EMBEDDING_MODEL)
            dim = EmbeddingManager._model.get_sentence_embedding_dimension()
            print(f"   ✅ Loaded (dimension: {dim})")

    @property
    def model(self):
        return EmbeddingManager._model

    @property
    def dimension(self):
        return self.model.get_sentence_embedding_dimension()

    def embed_batch(self, texts, batch_size=64):
        """
        تبدیل لیست متن‌ها به بردار

        Args:
            texts: لیست رشته‌ها
            batch_size: سایز batch

        Returns:
            list[list[float]]: لیست بردارها
        """
        if not texts:
            return []
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # نرمال‌سازی برای cosine similarity
        )
        return embeddings.tolist()

    def embed_single(self, text):
        """تبدیل یک متن به بردار"""
        return self.embed_batch([text])[0]