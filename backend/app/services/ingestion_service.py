import hashlib
import tempfile
import os
from pathlib import Path
from loguru import logger
from pinecone import Pinecone
from app.core.config import settings
from app.services.llm_service import llm_service


class IngestionService:

    CHUNK_SIZE    = 2000
    CHUNK_OVERLAP = 200

    SUPPORTED_TYPES = {
        ".pdf", ".docx", ".txt",
        ".jpg", ".jpeg", ".png", ".webp",
    }

    IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}

    # Only extract images above this size — smaller ones are usually
    # decorative icons or bullets, not meaningful content
    MIN_IMAGE_BYTES = 10_000   # 10 KB

    def __init__(self):
        pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = pc.Index(settings.pinecone_index_name)
        logger.info("IngestionService ready — Pinecone index connected")

    # ------------------------------------------------------------------ #
    # Main entry point                                                     #
    # ------------------------------------------------------------------ #

    async def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
        document_id: str,
    ) -> dict:
        ext = Path(filename).suffix.lower()

        if ext not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                f"Accepted: PDF, DOCX, TXT, JPG, PNG, WEBP"
            )

        logger.info(f"Ingestion start | file={filename} | user={user_id}")

        # Route to image pipeline or document pipeline
        if ext in self.IMAGE_TYPES:
            chunks = await self._process_standalone_image(
                file_bytes, filename, ext
            )
        else:
            chunks = await self._process_document(file_bytes, filename, ext)

        if not chunks:
            raise ValueError("No content could be extracted from this file.")

        logger.info(f"Total chunks to embed: {len(chunks)}")

        vectors = await self._embed_chunks(chunks, document_id, filename, user_id)

        namespace = f"user-{user_id}"
        self.index.upsert(vectors=vectors, namespace=namespace)
        logger.info(f"Upserted {len(vectors)} vectors → namespace '{namespace}'")

        return {
            "document_id": document_id,
            "filename":    filename,
            "chunks":      len(chunks),
        }

    async def delete_document(self, document_id: str, user_id: str) -> None:
        namespace = f"user-{user_id}"
        self.index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=namespace,
        )
        logger.info(f"Deleted vectors for document {document_id}")

    # ------------------------------------------------------------------ #
    # Document processing (PDF, DOCX, TXT)                                #
    # ------------------------------------------------------------------ #

    async def _process_document(
        self, file_bytes: bytes, filename: str, ext: str
    ) -> list[dict]:
        """
        Returns a list of chunk dicts, each with 'text' and 'chunk_type'.
        Text chunks come from the document body.
        Image chunks come from embedded images described by vision model.
        """
        all_chunks = []

        if ext == ".pdf":
            text, image_descriptions = await self._parse_pdf_with_images(file_bytes)
        elif ext == ".docx":
            text = self._parse_docx(file_bytes)
            image_descriptions = []
        elif ext == ".txt":
            text = file_bytes.decode("utf-8", errors="ignore")
            image_descriptions = []

        # Text chunks
        if text.strip():
            text_chunks = self._chunk_text(text)
            for chunk in text_chunks:
                all_chunks.append({
                    "text":       chunk,
                    "chunk_type": "text",
                })

        # Image description chunks
        for i, desc in enumerate(image_descriptions):
            if desc and len(desc) > 20:
                all_chunks.append({
                    "text":       f"[Image {i+1} from document]: {desc}",
                    "chunk_type": "image_description",
                })

        logger.info(
            f"Document processed | "
            f"text_chunks={len(all_chunks) - len(image_descriptions)} | "
            f"image_chunks={len(image_descriptions)}"
        )
        return all_chunks

    async def _process_standalone_image(
        self, file_bytes: bytes, filename: str, ext: str
    ) -> list[dict]:
        """Process a standalone image file uploaded directly by the user."""
        logger.info(f"Processing standalone image: {filename}")

        # Map extension to MIME subtype
        ext_to_mime = {
            ".jpg":  "jpeg",
            ".jpeg": "jpeg",
            ".png":  "png",
            ".webp": "webp",
        }
        mime = ext_to_mime.get(ext, "jpeg")

        description = await llm_service.describe_image(file_bytes, mime)

        return [{
            "text":       f"[Image: {filename}]: {description}",
            "chunk_type": "image_description",
        }]

    # ------------------------------------------------------------------ #
    # PDF parsing with image extraction                                    #
    # ------------------------------------------------------------------ #

    async def _parse_pdf_with_images(
        self, file_bytes: bytes
    ) -> tuple[str, list[str]]:
        """
        Parse a PDF using pymupdf.
        Returns (full_text, list_of_image_descriptions).
        """
        import fitz  # pymupdf

        text_pages = []
        image_descriptions = []

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            doc = fitz.open(tmp_path)

            for page_num, page in enumerate(doc):
                # Extract text from this page
                page_text = page.get_text()
                if page_text.strip():
                    text_pages.append(page_text)

                # Extract images from this page
                image_list = page.get_images(full=True)

                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]
                    try:
                        base_image  = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext   = base_image["ext"]  # 'jpeg', 'png', etc.

                        # Skip tiny images — likely decorative
                        if len(image_bytes) < self.MIN_IMAGE_BYTES:
                            logger.debug(
                                f"Skipping small image on page {page_num+1} "
                                f"({len(image_bytes)} bytes)"
                            )
                            continue

                        logger.info(
                            f"Processing image {img_index+1} on page {page_num+1} "
                            f"({len(image_bytes):,} bytes)"
                        )

                        description = await llm_service.describe_image(
                            image_bytes, image_ext
                        )
                        image_descriptions.append(description)

                    except Exception as e:
                        logger.warning(
                            f"Failed to process image {img_index+1} "
                            f"on page {page_num+1}: {e}"
                        )
                        continue

            doc.close()

        finally:
            os.unlink(tmp_path)

        full_text = "\n\n".join(text_pages)
        logger.info(
            f"PDF parsed | pages={len(text_pages)} | "
            f"images_described={len(image_descriptions)}"
        )
        return full_text, image_descriptions

    def _parse_docx(self, file_bytes: bytes) -> str:
        from docx import Document as DocxDocument
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            doc = DocxDocument(tmp_path)
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paras)
        finally:
            os.unlink(tmp_path)

    # ------------------------------------------------------------------ #
    # Chunking                                                             #
    # ------------------------------------------------------------------ #

    def _chunk_text(self, text: str) -> list[str]:
        chunks = []
        start  = 0
        while start < len(text):
            end   = start + self.CHUNK_SIZE
            chunk = text[start:end]
            if end < len(text):
                last_period = chunk.rfind(". ")
                if last_period > self.CHUNK_SIZE // 2:
                    end   = start + last_period + 1
                    chunk = text[start:end]
            chunk = chunk.strip()
            if len(chunk) > 50:
                chunks.append(chunk)
            start = end - self.CHUNK_OVERLAP
        return chunks

    # ------------------------------------------------------------------ #
    # Embedding                                                            #
    # ------------------------------------------------------------------ #

    async def _embed_chunks(
        self,
        chunks: list[dict],
        document_id: str,
        filename: str,
        user_id: str,
    ) -> list[dict]:
        vectors = []

        for i, chunk in enumerate(chunks):
            embedding = await llm_service.get_embedding(chunk["text"])

            vector_id = hashlib.md5(
                f"{document_id}-chunk-{i}".encode()
            ).hexdigest()

            vectors.append({
                "id":     vector_id,
                "values": embedding,
                "metadata": {
                    "document_id": document_id,
                    "filename":    filename,
                    "user_id":     user_id,
                    "chunk_index": i,
                    "chunk_type":  chunk.get("chunk_type", "text"),
                    "text":        chunk["text"],
                },
            })

            if (i + 1) % 5 == 0:
                logger.info(f"Embedded {i+1}/{len(chunks)} chunks")

        return vectors


ingestion_service = IngestionService()