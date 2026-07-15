import hashlib
import tempfile
import os
from pathlib import Path
from loguru import logger
from pypdf import PdfReader
from docx import Document as DocxDocument
from pinecone import Pinecone
from app.core.config import settings
from app.services.llm_service import llm_service


class IngestionService:

    # How many characters per chunk (roughly 500 words ≈ 2000 chars)
    CHUNK_SIZE     = 700
    # How many characters to repeat between chunks so nothing is lost at boundaries
    CHUNK_OVERLAP  = 100
    # File types we accept
    SUPPORTED_TYPES = {".pdf", ".docx", ".txt"}

    def __init__(self):
        pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = pc.Index(settings.pinecone_index_name)
        logger.info("IngestionService ready — Pinecone index connected")

    # ------------------------------------------------------------------ #
    # Main entry point — call this from the upload route                  #
    # ------------------------------------------------------------------ #

    async def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
        document_id: str,
    ) -> dict:
        """
        Full pipeline:
          file bytes → parse text → chunk → embed → upsert to Pinecone
        Returns a summary dict that the route can send back to the client.
        """
        ext = Path(filename).suffix.lower()

        if ext not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type '{ext}'. Accepted: PDF, DOCX, TXT")

        logger.info(f"Starting ingestion | file={filename} | user={user_id}")

        # Step 1 — parse raw text out of the file
        text = await self._parse(file_bytes, ext)

        if not text.strip():
            raise ValueError("The document appears to be empty or could not be read.")

        logger.info(f"Parsed {len(text)} characters from '{filename}'")

        # Step 2 — split into overlapping chunks
        chunks = self._chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks")

        # Step 3 — embed each chunk and build Pinecone vector records
        vectors = await self._embed_chunks(chunks, document_id, filename, user_id)

        # Step 4 — upsert all vectors into this user's private namespace
        namespace = f"user-{user_id}"
        self.index.upsert(vectors=vectors, namespace=namespace)
        logger.info(f"Upserted {len(vectors)} vectors into namespace '{namespace}'")

        return {
            "document_id": document_id,
            "filename": filename,
            "chunks": len(chunks),
        }

    async def delete_document(self, document_id: str, user_id: str) -> None:
        """
        Remove all Pinecone vectors that belong to this document.
        Called when a user deletes a document from their library.
        """
        namespace = f"user-{user_id}"
        self.index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=namespace,
        )
        logger.info(f"Deleted vectors for document {document_id} from namespace {namespace}")

    # ------------------------------------------------------------------ #
    # Step 1 — Parsing                                                    #
    # ------------------------------------------------------------------ #

    async def _parse(self, file_bytes: bytes, ext: str) -> str:
        if ext == ".pdf":
            return self._parse_pdf(file_bytes)
        elif ext == ".docx":
            return self._parse_docx(file_bytes)
        elif ext == ".txt":
            # TXT files are already plain text — just decode the bytes
            return file_bytes.decode("utf-8", errors="ignore")

    def _parse_pdf(self, file_bytes: bytes) -> str:
        """
        Write bytes to a temp file, read with pypdf, then delete the temp file.
        We use a temp file because pypdf needs a file path, not raw bytes.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            reader = PdfReader(tmp_path)
            pages = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            # Join pages with double newline so paragraph boundaries are preserved
            return "\n\n".join(pages)
        finally:
            # Always delete the temp file even if something crashes
            os.unlink(tmp_path)

    def _parse_docx(self, file_bytes: bytes) -> str:
        """Same pattern — temp file needed because python-docx needs a path."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            doc = DocxDocument(tmp_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        finally:
            os.unlink(tmp_path)

    # ------------------------------------------------------------------ #
    # Step 2 — Chunking                                                   #
    # ------------------------------------------------------------------ #

    def _chunk_text(self, text: str) -> list[str]:
        """
        Sliding window chunker.

        Example with CHUNK_SIZE=20 chars and CHUNK_OVERLAP=5:
          text = "The quick brown fox jumps over the lazy dog"
          chunk 1: "The quick brown fox " (chars 0-20)
          chunk 2: "fox jumps over the l" (chars 15-35)  ← 5 char overlap
          chunk 3: "the lazy dog"          (chars 30-end)

        The overlap ensures that if an important sentence falls right at a
        boundary, at least one of the two adjacent chunks will contain it fully.
        """
        chunks = []
        start  = 0

        while start < len(text):
            end   = start + self.CHUNK_SIZE
            chunk = text[start:end]

            # Try to end the chunk at a sentence boundary (". ")
            # so we don't cut a sentence in half
            if end < len(text):
                last_period = chunk.rfind(". ")
                if last_period > self.CHUNK_SIZE // 2:
                    # Found a good sentence boundary in the second half — use it
                    end   = start + last_period + 1
                    chunk = text[start:end]

            chunk = chunk.strip()
            # Skip tiny leftover fragments
            if len(chunk) > 50:
                chunks.append(chunk)

            # Move start forward but overlap by CHUNK_OVERLAP characters
            start = end - self.CHUNK_OVERLAP

        return chunks

    # ------------------------------------------------------------------ #
    # Step 3 — Embedding                                                  #
    # ------------------------------------------------------------------ #

    async def _embed_chunks(
        self,
        chunks: list[str],
        document_id: str,
        filename: str,
        user_id: str,
    ) -> list[dict]:
        """
        Embed each chunk one at a time and build the list of Pinecone records.

        Each Pinecone record has three parts:
          id     — a unique string ID for this vector
          values — the 3072-float embedding
          metadata — extra info stored alongside the vector so we can use it
                     later when we retrieve results (filename, chunk text, etc.)
        """
        vectors = []

        for i, chunk in enumerate(chunks):
            # Get the embedding from Azure text-embedding-3-large
            embedding = await llm_service.get_embedding(chunk)

            # Build a deterministic ID so re-ingesting the same doc
            # overwrites the old vectors rather than duplicating them
            vector_id = hashlib.md5(
                f"{document_id}-chunk-{i}".encode()
            ).hexdigest()

            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "document_id": document_id,
                    "filename":    filename,
                    "user_id":     user_id,
                    "chunk_index": i,
                    # Store the chunk text in metadata so we can retrieve it
                    # without a second database lookup.
                    # Pinecone metadata values are capped at 40KB — our chunks
                    # are ~2000 chars so we are well within the limit.
                    "text": chunk,
                },
            })

            # Small log every 10 chunks so you can see progress on large docs
            if (i + 1) % 10 == 0:
                logger.info(f"Embedded {i + 1}/{len(chunks)} chunks")

        return vectors


# Single shared instance — import this in your routes
ingestion_service = IngestionService()