"""
Document / file ingestion layer.

Active path (MVP): Claude-native parsing. Uploaded PDFs and images are sent
directly to Claude (which reads PDFs and images natively) with an extraction
prompt that pulls vibration-relevant parameters into structured fields.

Scaffolded paths (for later, per the architecture plan):
  - LlamaParse: AI-vision parsing of complex technical PDFs -> Markdown for RAG
  - Unstructured.io: PDF/DOCX/PPT/image -> structured JSON elements
Both are stubbed with clear TODOs and a consistent return contract so they can
be dropped in without touching the rest of the app.
"""

import base64
import os
from typing import Optional


# --------------------------------------------------------------------------- #
# Active: Claude-native extraction
# --------------------------------------------------------------------------- #
EXTRACTION_SYSTEM = """\
You are extracting vibration-test-relevant parameters from an uploaded document \
(a mission spec, launch vehicle user's guide excerpt, ICD, or test article \
datasheet). Return ONLY a compact JSON object with any of these keys you can \
find (omit keys you cannot determine; never invent values):
{
  "launch_vehicle": str,
  "orbit": str,
  "test_article_name": str,
  "mass_kg": number,
  "envelope_mm": str,
  "random_vibration_psd": str,   // any stated PSD breakpoints / Grms
  "sine_environment": str,
  "quasi_static_g": str,
  "shock_srs": str,
  "min_structural_freq_hz": number,
  "mounting_interface": str,     // bolt pattern, hole count/size if stated
  "operating_modes": str,
  "notes": str
}
Output the JSON and nothing else."""


def _encode_file(path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for a PDF or image."""
    ext = os.path.splitext(path)[1].lower()
    media = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext)
    if media is None:
        raise ValueError(f"Unsupported file type for extraction: {ext}")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media


def extract_with_claude(path: str, api_key: Optional[str] = None) -> dict:
    """
    Send the file to Claude and parse the returned JSON.
    Returns {"ok": bool, "data": dict|None, "raw": str, "error": str|None}.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"ok": False, "data": None, "raw": "",
                "error": "No ANTHROPIC_API_KEY set; cannot parse documents."}

    try:
        import json
        import anthropic
        data, media = _encode_file(path)

        if media == "application/pdf":
            source_block = {"type": "document",
                            "source": {"type": "base64",
                                       "media_type": media, "data": data}}
        else:
            source_block = {"type": "image",
                            "source": {"type": "base64",
                                       "media_type": media, "data": data}}

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=1500,
            system=EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": [
                source_block,
                {"type": "text",
                 "text": "Extract the vibration-relevant parameters as JSON."},
            ]}],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        # strip code fences if present
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        return {"ok": True, "data": parsed, "raw": raw, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "data": None, "raw": "", "error": str(e)}


# --------------------------------------------------------------------------- #
# Scaffolded: LlamaParse (TODO - requires LLAMA_CLOUD_API_KEY)
# --------------------------------------------------------------------------- #
def extract_with_llamaparse(path: str) -> dict:
    """
    TODO (post-MVP): use LlamaParse for AI-vision parsing of complex technical
    PDFs into Markdown, then index with LlamaIndex for RAG.

        from llama_parse import LlamaParse
        parser = LlamaParse(api_key=os.environ["LLAMA_CLOUD_API_KEY"],
                            result_type="markdown",
                            parsing_instruction="Extract test requirements "
                                                 "and acceptance criteria.")
        docs = parser.load_data(path)
        return {"ok": True, "markdown": docs[0].text, ...}
    """
    return {"ok": False, "data": None, "raw": "",
            "error": "LlamaParse not configured (scaffold). "
                     "Set LLAMA_CLOUD_API_KEY and implement."}


# --------------------------------------------------------------------------- #
# Scaffolded: Unstructured.io (TODO)
# --------------------------------------------------------------------------- #
def extract_with_unstructured(path: str) -> dict:
    """
    TODO (post-MVP): use Unstructured.io to break PDF/DOCX/PPT/image into
    structured elements (paragraphs, tables, lists, images) -> JSON for
    LangChain ingestion.

        from unstructured.partition.auto import partition
        elements = partition(filename=path)
        return {"ok": True, "elements": [el.to_dict() for el in elements], ...}
    """
    return {"ok": False, "data": None, "raw": "",
            "error": "Unstructured.io not configured (scaffold)."}
