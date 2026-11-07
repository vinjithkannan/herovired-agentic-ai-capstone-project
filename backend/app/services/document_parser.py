from pathlib import Path
from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


def extract_text(path: str, extension: str) -> str:
    ext = extension.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF, DOCX, MD or TXT.")
    if ext == ".pdf":
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)
    elif ext == ".docx":
        doc = DocxDocument(path)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        text = "\n".join(parts)
    else:
        text = Path(path).read_text(encoding="utf-8-sig")
    text = text.strip()
    if not text:
        raise ValueError("No extractable text found. If this is a scanned PDF, OCR is required.")
    return text


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[str]:
    """Simple character-window chunker with whitespace-aware boundaries."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0")
    normalized = " ".join(text.split())
    chunks, start, length = [], 0, len(normalized)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = normalized.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks
