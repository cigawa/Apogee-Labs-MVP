"""
Lightweight TF-IDF retrieval over the vibration standards corpus.

MVP choice: scikit-learn TF-IDF, zero external infra. The interface mirrors
what you'd get from LlamaIndex's retriever, so swapping to LlamaIndex +
VectorStore later (as in the architecture plan) is a localized change.
"""

from dataclasses import dataclass
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from vibration import VIBRATION_CHUNKS


@dataclass
class RetrievedChunk:
    id: str
    source: str
    topic: str
    text: str
    score: float


class VibrationRetriever:
    def __init__(self):
        self.chunks = VIBRATION_CHUNKS
        self._docs = [f"{c['topic']} {c['text']}" for c in self.chunks]
        self._vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), min_df=1
        )
        self._matrix = self._vectorizer.fit_transform(self._docs)

    def search(self, query: str, k: int = 6) -> List[RetrievedChunk]:
        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix)[0]
        order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
        return [
            RetrievedChunk(
                id=self.chunks[i]["id"], source=self.chunks[i]["source"],
                topic=self.chunks[i]["topic"], text=self.chunks[i]["text"],
                score=float(sims[i]),
            )
            for i in order
        ]

    def all_chunks(self) -> List[RetrievedChunk]:
        return [
            RetrievedChunk(id=c["id"], source=c["source"], topic=c["topic"],
                           text=c["text"], score=1.0)
            for c in self.chunks
        ]
