# Knowledge Base — drop your RAG documents here

Put PDFs, .txt, .md, or .docx files in this folder. On the next app run, the
LlamaIndex pipeline ingests, chunks, embeds, and indexes them automatically,
and retrieval switches from the curated TF-IDF corpus to semantic search over
these real documents.

## What to add first (all public)

- NASA-STD-7001 (Payload Vibroacoustic Test Criteria) — standards.nasa.gov
- GEVS GSFC-STD-7000 (General Environmental Verification Standard)
- NASA-HDBK-7004 / 7005 (Force Limited Vibration / Dynamic Criteria)
- MIL-STD-1540 (Test Requirements for Space Vehicles)
- Launch vehicle payload user's guides (Falcon 9, Electron, Vulcan, etc.)
- Public CubeSat test reports and university test plans (from NTRS: ntrs.nasa.gov)

## After adding documents

1. First run rebuilds the index (slow once; cached afterward to rag_store/).
2. To force a rebuild after adding/removing files, delete the rag_store/ folder
   or run:  python rag_index.py --rebuild

## Note on privacy

The default embedding model runs locally (BAAI/bge-small-en-v1.5) — no document
text leaves your environment. This matters as you add proprietary customer test
data later. Set APOGEE_EMBED_BACKEND=openai to use a hosted embedder instead.
