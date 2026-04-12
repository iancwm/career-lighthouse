# api/services/ingestion.py
import uuid
from datetime import datetime, timezone


def parse_file(content: bytes, filename: str) -> str:
    """Extract text from PDF, DOCX, or plain text."""
    if filename.lower().endswith(".pdf"):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif filename.lower().endswith(".docx"):
        import io
        from docx import Document
        from docx.oxml.ns import qn
        doc = Document(io.BytesIO(content))
        parts = []
        for block in doc.element.body:
            if block.tag == qn('w:p'):
                # Paragraph — collect run text
                text = "".join(
                    run.text for run in block.iter(qn('w:t'))
                    if run.text
                )
                if text.strip():
                    parts.append(text)
            elif block.tag == qn('w:tbl'):
                # Table — format as pipe-delimited rows
                rows = []
                for row in block.iter(qn('w:tr')):
                    cells = []
                    for cell in row.iter(qn('w:tc')):
                        cell_text = "".join(
                            t.text for t in cell.iter(qn('w:t')) if t.text
                        ).strip()
                        cells.append(cell_text)
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    parts.append("\n".join(rows))
        return "\n".join(parts)
    else:
        return content.decode("utf-8", errors="replace")


def chunk_text(text: str, max_tokens: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping word-based chunks (approx 1 word ≈ 1.3 tokens)."""
    words = text.split()
    word_limit = int(max_tokens / 1.3)
    overlap_words = int(overlap / 1.3)
    if len(words) <= word_limit:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + word_limit, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += word_limit - overlap_words
    return chunks


def prepare_document(file_content: bytes, filename: str, embedder) -> list[dict]:
    """Parse, chunk, and embed a document. Returns list of point dicts (without storing).

    Separating preparation from storage allows callers to run deduplication checks
    (or other pre-storage logic) before committing chunks to the vector store.
    """
    text = parse_file(file_content, filename)
    chunks = chunk_text(text)
    if not chunks:
        return []

    vectors = embedder.encode_batch(chunks)
    timestamp = datetime.now(timezone.utc).isoformat()

    return [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filename}-{i}")),
            "vector": vectors[i],
            "payload": {
                "source_filename": filename,
                "chunk_index": i,
                "upload_timestamp": timestamp,
                "text": chunk,
            },
        }
        for i, chunk in enumerate(chunks)
    ]


def ingest_document(file_content: bytes, filename: str, embedder, store) -> int:
    """Parse, chunk, embed, and store a document. Returns chunk count.

    Convenience wrapper around prepare_document + store.upsert.
    Use prepare_document directly when pre-storage checks are needed.
    """
    points = prepare_document(file_content, filename, embedder)
    if not points:
        return 0
    store.upsert(points)
    return len(points)
