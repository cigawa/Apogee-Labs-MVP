"""
Unified retrieval layer.

Picks the best available backend automatically:
  - If a knowledge_base/ folder with documents exists AND llama-index is
    installed -> use semantic LlamaIndex RAG over real documents.
  - Otherwise -> fall back to the original TF-IDF retriever over the curated
    vibration corpus (always works, no heavy deps).

Both return the same RetrievedChunk shape, so main.py / prompt builders never
change. This lets you adopt LlamaIndex gradually: drop PDFs into knowledge_base/
and the app upgrades itself on next run.
"""

import os
from typing import List

# Reuse the simple retriever's chunk type as the common contract
from retriever import VibrationRetriever, RetrievedChunk

_KB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "knowledge_base")


def _kb_has_documents() -> bool:
    if not os.path.isdir(_KB_DIR):
        return False
    for root, _dirs, files in os.walk(_KB_DIR):
        for f in files:
            if f.lower().endswith((".pdf", ".txt", ".md", ".docx")):
                return True
    return False


def _llama_available() -> bool:
    try:
        import llama_index.core  # noqa: F401
        return True
    except Exception:
        return False


class UnifiedRetriever:
    """Chooses LlamaIndex semantic RAG when possible, else TF-IDF."""

    def __init__(self):
        self.backend = "tfidf"
        self._tfidf = VibrationRetriever()
        self._llama_index = None

        if _kb_has_documents() and _llama_available():
            try:
                from rag_index import build_or_load_index
                self._llama_index = build_or_load_index()
                self.backend = "llamaindex"
            except Exception as e:  # noqa: BLE001
                # Any ingestion/embedding failure -> stay on TF-IDF
                print(f"[retriever] LlamaIndex unavailable, using TF-IDF: {e}")
                self.backend = "tfidf"

    def search(self, query: str, k: int = 6) -> List[RetrievedChunk]:
        if self.backend == "llamaindex" and self._llama_index is not None:
            from rag_index import retrieve
            return retrieve(self._llama_index, query, k=k)
        return self._tfidf.search(query, k=k)

    def all_chunks(self) -> List[RetrievedChunk]:
        # For the curated corpus we can pass everything; for LlamaIndex we
        # retrieve a broad set instead (there's no "all" for a big index).
        if self.backend == "llamaindex" and self._llama_index is not None:
            from rag_index import retrieve
            return retrieve(self._llama_index,
                            "vibration test fixture profile requirements "
                            "qualification notching", k=8)
        return self._tfidf.all_chunks()
