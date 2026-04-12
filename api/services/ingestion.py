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


def _is_table_line(line: str) -> bool:
    """Return True if the line looks like a pipe-delimited table row."""
    return line.startswith("|") and "|" in line[1:]


def _is_list_item(line: str) -> bool:
    """Return True if the line looks like a markdown list item."""
    stripped = line.lstrip()
    return stripped.startswith(("- ", "* "))


def _split_at_boundaries(text: str) -> list[str]:
    """Split text into semantic blocks: paragraphs, tables, and lists.

    A paragraph is separated from the next by one or more blank lines.
    A table is a sequence of consecutive pipe-delimited lines.
    A list is a sequence of consecutive list-item lines.
    """
    lines = text.split("\n")
    blocks: list[str] = []
    current: list[str] = []
    current_type: str | None = None  # "paragraph", "table", or "list"

    def flush():
        if current:
            blocks.append("\n".join(current))
            current.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Blank line — boundary between semantic units
            flush()
            current_type = None
            continue

        if _is_table_line(stripped):
            if current_type not in ("table",):
                flush()
            current_type = "table"
            current.append(line)
        elif _is_list_item(stripped):
            if current_type not in ("list",):
                flush()
            current_type = "list"
            current.append(line)
        else:
            if current_type not in ("paragraph",):
                flush()
            current_type = "paragraph"
            current.append(line)

    flush()
    return blocks


def chunk_text(text: str, max_tokens: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping chunks, respecting semantic boundaries.

    Strategy:
    1. Split text into semantic blocks (paragraphs, tables, lists).
    2. For each block, if it fits within max_tokens, keep it whole.
    3. If a block exceeds max_tokens, split it at word boundaries.
    4. Apply overlap between consecutive chunks.

    Fallback: if no semantic boundaries exist (single long paragraph),
    splits at word boundaries (original behavior).
    """
    if not text.strip():
        return []

    words = text.split()
    word_limit = int(max_tokens / 1.3)
    overlap_words = int(overlap / 1.3)

    # If entire text fits in one chunk, return as-is
    if len(words) <= word_limit:
        return [text]

    # Step 1: split into semantic blocks
    blocks = _split_at_boundaries(text)

    # Step 2: build chunks from blocks, splitting oversized blocks
    chunks: list[str] = []
    for block in blocks:
        block_words = block.split()
        if len(block_words) <= word_limit:
            # Block fits — add as a chunk (will be merged with overlap below)
            chunks.append(block)
        else:
            # Block too large — split at word boundaries
            start = 0
            while start < len(block_words):
                end = min(start + word_limit, len(block_words))
                chunk_text_part = " ".join(block_words[start:end])
                chunks.append(chunk_text_part)
                if end == len(block_words):
                    break
                start += word_limit - overlap_words

    # Step 3: apply overlap between consecutive chunks
    # Re-split with overlap on the full text, but use semantic boundaries
    # to decide chunk start points
    if len(chunks) <= 1:
        return chunks

    # Merge small consecutive chunks that together fit within the limit
    merged: list[str] = []
    for chunk in chunks:
        if not merged:
            merged.append(chunk)
            continue
        combined = merged[-1] + " " + chunk
        if len(combined.split()) <= word_limit:
            merged[-1] = combined
        else:
            merged.append(chunk)

    # Final pass: ensure overlap between consecutive chunks
    final: list[str] = []
    for i, chunk in enumerate(merged):
        if i > 0 and overlap_words > 0:
            prev_words = merged[i - 1].split()
            overlap_text = " ".join(prev_words[-overlap_words:])
            chunk = overlap_text + " " + chunk
        final.append(chunk)

    return final if final else [text]


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
