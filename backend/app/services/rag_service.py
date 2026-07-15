from typing import AsyncGenerator
from loguru import logger
from pinecone import Pinecone
from app.core.config import settings
from app.services.llm_service import llm_service



SYSTEM_PROMPT = """You are DocuMind, an intelligent document assistant.

Your job is to answer questions using ONLY the context extracted from the user's documents.

Rules you must follow:
- If the answer is clearly in the context, answer it directly and cite which document it came from.
- If the context is partially relevant, answer what you can and say what you couldn't find.
- If the context has nothing relevant, say: "I couldn't find that information in your uploaded documents."
- Never make up information that isn't in the context.
- Be concise and precise. Avoid padding your answers.
- When quoting or referencing specific content, mention the source filename."""


class RAGService:
    """
    Retrieval-Augmented Generation pipeline.

    """

    # How many chunks to pull from Pinecone initially.
    # We fetch more than we need so the reranker has candidates to work with.
    RETRIEVE_TOP_K = 10

    # How many chunks to actually send to the LLM after reranking.
    # Sending too many wastes tokens and confuses the model.
    CONTEXT_TOP_N = 5

    # Minimum similarity score to include a chunk at all.
    # Chunks below this are almost certainly irrelevant — drop them.
    SCORE_THRESHOLD = 0.30

    def __init__(self):
        pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = pc.Index(settings.pinecone_index_name)
        logger.info("RAGService ready")

    

    async def query_stream(
        self,
        question: str,
        user_id: str,
        chat_history: list[dict] | None = None,
        document_ids: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Full RAG pipeline. Yields string tokens for SSE streaming.

        Args:
            question:     The user's question as a plain string.
            user_id:      Scopes the Pinecone search to this user's namespace.
            chat_history: Last N turns of conversation for follow-up questions.
            document_ids: If provided, search only these docs. None = all docs.
        """

        # Step 1 — embed the question
        logger.info(f"RAG query | user={user_id} | question='{question[:60]}...'")
        query_embedding = await llm_service.get_embedding(question)

        # Step 2 — retrieve candidate chunks from Pinecone
        chunks = self._retrieve(query_embedding, user_id, document_ids)

        if not chunks:
            yield "I couldn't find any relevant information in your uploaded documents for that question."
            return

        # Step 3 — rerank (passthrough for now, reranker drops in here later)
        chunks = self._rerank(question, chunks)

        # Step 4 — trim to top N after reranking
        chunks = chunks[: self.CONTEXT_TOP_N]

        # Step 5 — build the context string and full message list
        context  = self._build_context(chunks)
        messages = self._build_messages(question, context, chat_history)

        # Log which sources we're using
        sources = list({c["filename"] for c in chunks})
        logger.info(f"Answering from {len(chunks)} chunks | sources: {sources}")

        # Step 6 — stream tokens from LLM (Azure → Groq fallback is inside llm_service)
        async for token in llm_service.chat_stream(messages):
            yield token

        # Step 7 — append a sources footer after the full answer
        sources_line = "\n\n---\n**Sources:** " + ", ".join(sources)
        yield sources_line

    # ------------------------------------------------------------------ #
    # Step 2 — Retrieval                                                  #
    # ------------------------------------------------------------------ #

    def _retrieve(
        self,
        embedding: list[float],
        user_id: str,
        document_ids: list[str] | None,
    ) -> list[dict]:
        """
        Query Pinecone within the user's private namespace.
        Returns a list of chunk dicts sorted by similarity score (highest first).
        """
        namespace = f"user-{user_id}"

        query_kwargs = {
            "vector":          embedding,
            "top_k":           self.RETRIEVE_TOP_K,
            "include_metadata": True,
            "namespace":       namespace,
        }

        # If the user is asking about specific documents, filter to those only
        if document_ids:
            query_kwargs["filter"] = {
                "document_id": {"$in": document_ids}
            }

        result = self.index.query(**query_kwargs)

        # Convert Pinecone match objects to plain dicts and filter low scores
        chunks = []
        for match in result.matches:
            if match.score < self.SCORE_THRESHOLD:
                continue
            chunks.append({
                "text":        match.metadata.get("text", ""),
                "filename":    match.metadata.get("filename", "unknown"),
                "document_id": match.metadata.get("document_id", ""),
                "chunk_index": match.metadata.get("chunk_index", 0),
                "score":       round(match.score, 4),
            })

        logger.info(
            f"Pinecone returned {len(result.matches)} matches, "
            f"{len(chunks)} above threshold {self.SCORE_THRESHOLD}"
        )
        return chunks

    # ------------------------------------------------------------------ #
    # Step 3 — Rerank slot                                                #
    # ------------------------------------------------------------------ #

    def _rerank(self, question: str, chunks: list[dict]) -> list[dict]:
        """
        Reranking slot. Currently a passthrough — returns chunks unchanged.

        TO ADD RERANKING LATER:
        Option A — Cohere reranker (best quality, 1 API call):
            import cohere
            co = cohere.Client(api_key)
            results = co.rerank(
                query=question,
                documents=[c["text"] for c in chunks],
                model="rerank-english-v3.0",
                top_n=self.CONTEXT_TOP_N,
            )
            return [chunks[r.index] for r in results.results]

        Option B — local cross-encoder (free, slower):
            from sentence_transformers import CrossEncoder
            model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            pairs = [(question, c["text"]) for c in chunks]
            scores = model.predict(pairs)
            ranked = sorted(zip(scores, chunks), reverse=True)
            return [c for _, c in ranked]
        """
        # Passthrough — Pinecone cosine similarity order is preserved
        return chunks

    # ------------------------------------------------------------------ #
    # Step 5a — Build context string                                      #
    # ------------------------------------------------------------------ #

    def _build_context(self, chunks: list[dict]) -> str:
        """
        Format retrieved chunks into a readable context block for the LLM.
        Each chunk is numbered and labelled with its source filename.
        """
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[{i}] From '{chunk['filename']}' "
                f"(similarity: {chunk['score']}):\n{chunk['text']}"
            )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    # Step 5b — Build message list                                        #
    # ------------------------------------------------------------------ #

    def _build_messages(
        self,
        question: str,
        context: str,
        chat_history: list[dict] | None,
    ) -> list[dict]:
        """
        Assemble the full message list for the LLM.

        Structure:
          [system prompt]
          [last 6 turns of chat history]  ← gives memory for follow-up questions
          [user message with injected context]
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inject recent history so follow-up questions work naturally.
        # "What did it say about X?" needs to know what "it" refers to.
        if chat_history:
            # Only use the last 6 turns (3 user + 3 assistant) to stay within token limits
            messages.extend(chat_history[-6:])

        # The final user message contains both the context AND the question.
        # The model sees: "here are the relevant document excerpts, now answer this"
        user_content = (
            f"Context from your documents:\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"Question: {question}"
        )
        messages.append({"role": "user", "content": user_content})

        return messages


# Single shared instance — import this in your chat route
rag_service = RAGService()