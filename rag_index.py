"""
LlamaIndex RAG pipeline for Apogee — semantic retrieval over REAL documents.

This is the roadmap upgrade from the TF-IDF retriever:
  - INGEST:   read PDFs / text / markdown from a knowledge-base folder
  - INDEX:    chunk + embed each document, store vectors in a persistent index
  - RETRIEVE: semantic (meaning-based) search returns the most relevant chunks

Embedding model: defaults to a LOCAL HuggingFace model (free, private, no API).
Set APOGEE_EMBED_BACKEND=openai to use OpenAI embeddings instead.

The index is persisted to disk so you ingest ONCE, then query many times fast.

Install (CPU is fine):
    pip install llama-index-core llama-index-readers-file \\
                llama-index-embeddings-huggingface

Usage:
    from rag_index import build_or_load_index, retrieve
    idx = build_or_load_index("knowledge_base")        # ingest/index (cached)
    chunks = retrieve(idx, "qualification random vibration duration", k=6)
"""

import os
from dataclasses import dataclass
from typing import List

# Where documents live and where the built index is cached
DEFAULT_KB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "knowledge_base")
DEFAULT_INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "rag_store")

# Chunking: how documents get split before embedding
CHUNK_SIZE = 512        # tokens per chunk
CHUNK_OVERLAP = 64      # overlap so context isn't cut mid-thought


@dataclass
class RetrievedChunk:
    """Mirrors the shape returned by the old TF-IDF retriever so the rest of
    the app (prompt builders) doesn't have to change."""
    id: str
    source: str
    topic: str
    text: str
    score: float


# --------------------------------------------------------------------------- #
# Embedding model selection
# --------------------------------------------------------------------------- #
def _configure_embeddings():
    """Set the global LlamaIndex embedding model based on env config."""
    from llama_index.core import Settings

    # Default is now HOSTED embeddings (lightweight, no torch) so the app fits
    # within free-tier memory limits. Options: "openai" (default), "voyage",
    # or "local" (HuggingFace/torch — heavy, only for big-memory hosts).
    backend = os.environ.get("APOGEE_EMBED_BACKEND", "openai").lower()

    if backend == "voyage":
        # Voyage AI — Anthropic's recommended embeddings. Needs VOYAGE_API_KEY.
        from llama_index.embeddings.voyageai import VoyageEmbedding
        Settings.embed_model = VoyageEmbedding(
            model_name="voyage-3",
            voyage_api_key=os.environ.get("VOYAGE_API_KEY"),
        )
    elif backend == "local":
        # Local: free, private, but pulls in torch (large). Only use on a
        # host with plenty of memory (e.g. Hugging Face Spaces), NOT the
        # Streamlit Community Cloud free tier.
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-small-en-v1.5"
        )
    else:
        # Hosted OpenAI embeddings (default): cheap, tiny memory footprint.
        # Needs OPENAI_API_KEY.
        from llama_index.embeddings.openai import OpenAIEmbedding
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

    # We do retrieval only here; the LLM call happens in claude_client.
    # Disable LlamaIndex's own LLM so it doesn't require an extra key.
    Settings.llm = None
    Settings.chunk_size = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP


# --------------------------------------------------------------------------- #
# Build / load the index
# --------------------------------------------------------------------------- #
def build_or_load_index(kb_dir: str = DEFAULT_KB_DIR,
                        index_dir: str = DEFAULT_INDEX_DIR,
                        force_rebuild: bool = False):
    """
    Build a vector index from documents in kb_dir, or load the cached one.

    Returns a LlamaIndex VectorStoreIndex. Call retrieve() on it.
    """
    from llama_index.core import (VectorStoreIndex, SimpleDirectoryReader,
                                  StorageContext, load_index_from_storage)

    _configure_embeddings()

    # Load cached index if present and not forcing a rebuild
    if not force_rebuild and os.path.isdir(index_dir) and os.listdir(index_dir):
        storage = StorageContext.from_defaults(persist_dir=index_dir)
        return load_index_from_storage(storage)

    # Otherwise ingest documents and build a fresh index
    if not os.path.isdir(kb_dir) or not os.listdir(kb_dir):
        raise FileNotFoundError(
            f"Knowledge base folder '{kb_dir}' is empty. Add PDFs / .txt / .md "
            "files (NASA-STD-7001, launch vehicle user's guides, test reports) "
            "and try again."
        )

    # SimpleDirectoryReader auto-handles .pdf, .txt, .md, .docx, etc.
    documents = SimpleDirectoryReader(
        input_dir=kb_dir, recursive=True
    ).load_data()

    index = VectorStoreIndex.from_documents(documents, show_progress=True)
    os.makedirs(index_dir, exist_ok=True)
    index.storage_context.persist(persist_dir=index_dir)
    return index


# --------------------------------------------------------------------------- #
# Retrieve
# --------------------------------------------------------------------------- #
def retrieve(index, query: str, k: int = 6) -> List[RetrievedChunk]:
    """Semantic retrieval. Returns RetrievedChunk objects (same shape as the
    old retriever) so prompt-building code is unchanged."""
    retriever = index.as_retriever(similarity_top_k=k)
    nodes = retriever.retrieve(query)

    out: List[RetrievedChunk] = []
    for n in nodes:
        meta = n.node.metadata or {}
        source = meta.get("file_name", meta.get("source", "document"))
        out.append(RetrievedChunk(
            id=n.node.node_id,
            source=source,
            topic=meta.get("topic", "retrieved passage"),
            text=n.node.get_content(),
            score=float(n.score) if n.score is not None else 0.0,
        ))
    return out


# --------------------------------------------------------------------------- #
# Optional CLI for ingestion / quick test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    print("Building/loading index from:", DEFAULT_KB_DIR)
    idx = build_or_load_index(force_rebuild="--rebuild" in sys.argv)
    q = "qualification random vibration level and duration per axis"
    print(f"\nQuery: {q}\n")
    for c in retrieve(idx, q, k=4):
        print(f"[{c.source}] score={c.score:.3f}")
        print(c.text[:200].replace("\n", " "), "...\n")
