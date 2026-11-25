"""
FinSight AI — Vector Store and RAG Document Embeddings
Integrates ChromaDB and Sentence-Transformers for semantic financial research.
"""

import os
from typing import List, Dict, Optional
from app.config import settings


class FinancialVectorStore:
    def __init__(self):
        self.chroma_path = settings.chromadb_path
        os.makedirs(self.chroma_path, exist_ok=True)
        self._client = None
        self._collection = None
        self._embedder = None

    def _init_components(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            self._client = chromadb.PersistentClient(path=self.chroma_path)
            self._collection = self._client.get_or_create_collection(name="financial_docs")

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self._embedder = None
        return self._embedder

    def add_documents(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Index financial report excerpts, SEC filings, or news articles."""
        self._init_components()
        embedder = self._get_embedder()

        if embedder:
            embeddings = embedder.encode(documents).tolist()
            self._collection.upsert(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
        else:
            self._collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

    def query(self, query_text: str, n_results: int = 3, filter_dict: Optional[Dict] = None) -> List[Dict]:
        """Perform semantic retrieval."""
        self._init_components()
        embedder = self._get_embedder()

        kwargs = {"n_results": n_results}
        if filter_dict:
            kwargs["where"] = filter_dict

        if embedder:
            q_emb = embedder.encode([query_text]).tolist()
            results = self._collection.query(query_embeddings=q_emb, **kwargs)
        else:
            results = self._collection.query(query_texts=[query_text], **kwargs)

        items = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            for doc, meta in zip(docs, metas):
                items.append({"content": doc, "metadata": meta})
        return items
