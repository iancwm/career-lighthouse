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
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
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


def ingest_document(file_content: bytes, filename: str, embedder, store) -> int:
    """Parse, chunk, embed, and store a document. Returns chunk count."""
    text = parse_file(file_content, filename)
    chunks = chunk_text(text)
    if not chunks:
        return 0

    vectors = embedder.encode_batch(chunks)
    timestamp = datetime.now(timezone.utc).isoformat()

    points = [
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
    store.upsert(points)
    return len(chunks)
