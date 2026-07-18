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

        # Step 1 — conversational check (greetings, small talk)
        if self._is_conversational(question):
            logger.info(f"Conversational query | user={user_id}")
            async for token in llm_service.chat_stream(
                self._build_conversational_messages(question, chat_history)
            ):
                yield token
            return

        # Step 2 — summary check (broad document overview requests)
        if self._is_summary_query(question):
            logger.info(f"Summary query detected | user={user_id}")
            async for token in self._handle_summary(
                question, user_id, document_ids, chat_history
            ):
                yield token
            return

        # Step 3 — normal RAG flow
        logger.info(f"RAG query | user={user_id} | question='{question[:60]}'")
        query_embedding = await llm_service.get_embedding(question)

        chunks = self._retrieve(query_embedding, user_id, document_ids)

        if not chunks:
            # One more attempt — broaden the search with a rephrased version
            chunks = await self._broad_retrieve(question, user_id, document_ids)

        if not chunks:
            yield (
                "I couldn't find relevant information in your uploaded documents "
                "for that question.\n\n"
                "**Try:**\n"
                "- Rephrasing with more specific terms\n"
                "- Checking that the right document is uploaded\n"
                "- Asking about a specific section or topic in the document"
            )
            return

        chunks = self._rerank(question, chunks)
        chunks = chunks[: self.CONTEXT_TOP_N]

        context  = self._build_context(chunks)
        messages = self._build_messages(question, context, chat_history)

        sources = list({c["filename"] for c in chunks})
        logger.info(f"Answering from {len(chunks)} chunks | sources: {sources}")

        async for token in llm_service.chat_stream(messages):
            yield token

        yield "\n\n---\n**Sources:** " + ", ".join(sources)
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
    

    async def _handle_summary(
        self,
        question: str,
        user_id: str,
        document_ids: list[str] | None,
        chat_history: list[dict] | None,
    ) -> AsyncGenerator[str, None]:
        """
        For summary queries, we don't search for a specific answer.
        Instead we fetch a broad spread of chunks from across the document
        and ask the LLM to synthesize an overview.
        """
        namespace = f"user-{user_id}"

        # Build a generic embedding that retrieves a spread of content
        # We use a neutral query that will match diverse chunks
        broad_queries = [
            "introduction overview main topic",
            "key points conclusions summary",
            "important details findings results",
        ]

        all_chunks = []
        seen_ids   = set()

        for q in broad_queries:
            embedding = await llm_service.get_embedding(q)

            query_kwargs = {
                "vector":           embedding,
                "top_k":            6,
                "include_metadata": True,
                "namespace":        namespace,
            }
            if document_ids:
                query_kwargs["filter"] = {"document_id": {"$in": document_ids}}

            result = self.index.query(**query_kwargs)

            for match in result.matches:
                if match.score < 0.10 and match.metadata.get("chunk_index") not in seen_ids:
                    continue
                chunk_key = match.metadata.get("chunk_index", 0)
                if chunk_key not in seen_ids:
                    seen_ids.add(chunk_key)
                    all_chunks.append({
                        "text":        match.metadata.get("text", ""),
                        "filename":    match.metadata.get("filename", "unknown"),
                        "document_id": match.metadata.get("document_id", ""),
                        "chunk_index": match.metadata.get("chunk_index", 0),
                        "score":       match.score,
                    })

        if not all_chunks:
            yield (
                "I wasn't able to retrieve enough content to summarize. "
                "Please make sure your document has been uploaded and processed successfully."
            )
            return

        # Sort by chunk index so the summary follows document order
        all_chunks.sort(key=lambda x: x["chunk_index"])

        # Take up to 10 chunks for the summary — more than normal RAG
        summary_chunks = all_chunks[:10]

        context = self._build_context(summary_chunks)
        sources = list({c["filename"] for c in summary_chunks})

        summary_prompt = (
            f"The user wants a summary of their document(s).\n\n"
            f"Here are excerpts from across the document in order:\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"Please provide a clear, well-structured summary covering:\n"
            f"- What the document is about\n"
            f"- The main topics or sections\n"
            f"- Key points, findings, or conclusions\n\n"
            f"User's request: {question}"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": summary_prompt},
        ]

        logger.info(
            f"Summary using {len(summary_chunks)} chunks | sources: {sources}"
        )

        async for token in llm_service.chat_stream(messages):
            yield token

        yield "\n\n---\n**Sources:** " + ", ".join(sources)

    async def _broad_retrieve(
        self,
        question: str,
        user_id: str,
        document_ids: list[str] | None,
    ) -> list[dict]:
        """
        Fallback retrieval with a lower threshold and rephrased query.
        Called when the normal retrieve returns nothing.
        This catches questions that are slightly off from document vocabulary.
        """
        namespace = f"user-{user_id}"

        # Rephrase the question to be more generic
        rephrased = f"information about {question}"
        embedding  = await llm_service.get_embedding(rephrased)

        query_kwargs = {
            "vector":           embedding,
            "top_k":            self.RETRIEVE_TOP_K,
            "include_metadata": True,
            "namespace":        namespace,
        }
        if document_ids:
            query_kwargs["filter"] = {"document_id": {"$in": document_ids}}

        result = self.index.query(**query_kwargs)

        # Use a much lower threshold for this fallback attempt
        chunks = []
        for match in result.matches:
            if match.score < 0.15:
                continue
            chunks.append({
                "text":        match.metadata.get("text", ""),
                "filename":    match.metadata.get("filename", "unknown"),
                "document_id": match.metadata.get("document_id", ""),
                "chunk_index": match.metadata.get("chunk_index", 0),
                "score":       round(match.score, 4),
            })

        logger.info(
            f"Broad retrieval fallback found {len(chunks)} chunks "
            f"for query='{question[:40]}'"
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
    
    def _is_conversational(self, question: str) -> bool:
        """
        Lightweight check — no API call, just string matching.
        Returns True if the question is clearly casual conversation
        that doesn't need document search.
        """
        q = question.lower().strip().rstrip("?!.")

        # Direct greetings and small talk
        conversational_phrases = {
            "hi", "hello", "hey", "hiya", "howdy",
            "how are you", "how are you doing", "how do you do",
            "what's up", "whats up", "sup",
            "good morning", "good afternoon", "good evening", "good night",
            "thanks", "thank you", "thank you so much", "cheers",
            "bye", "goodbye", "see you", "see ya", "later",
            "who are you", "what are you", "what can you do",
            "help", "what is documind", "tell me about yourself",
        }

        if q in conversational_phrases:
            return True

        # Short inputs under 4 words that aren't document questions
        words = q.split()
        if len(words) <= 3:
            # These short patterns are almost never document questions
            greet_starters = ("hi", "hey", "hello", "thanks", "ok", "okay", "cool", "great")
            if words[0] in greet_starters:
                return True

        return False
    
    def _is_summary_query(self, question: str) -> bool:
        """
        Detects when the user wants a summary or overview of the document
        rather than a specific factual answer.
        """
        q = question.lower().strip()

        summary_patterns = [
            "summarize", "summarise", "summary",
            "overview", "give me an overview",
            "what is this document about", "what does this document say",
            "what is this about", "tell me about this document",
            "what are the main points", "what are the key points",
            "main topics", "key topics",
            "tldr", "tl;dr",
            "brief me", "brief summary",
            "explain this document", "explain the document",
            "what does it say", "what does it cover",
        ]

        return any(pattern in q for pattern in summary_patterns)

    def _build_conversational_messages(
        self,
        question: str,
        chat_history: list[dict] | None,
    ) -> list[dict]:
        """
        Builds messages for casual conversation — no document context injected.
        The model answers from its own knowledge.
        """
        system = (
            "You are DocuMind, a friendly and helpful AI document assistant. "
            "You help users chat with their uploaded documents. "
            "For casual conversation and greetings, respond naturally and briefly. "
            "If the user asks a general knowledge question not related to documents, "
            "you can answer it helpfully from your own knowledge and mention that "
            "you can also help them search through their uploaded documents."
        )
        messages = [{"role": "system", "content": system}]
        if chat_history:
            messages.extend(chat_history[-6:])
        messages.append({"role": "user", "content": question})
        return messages


# Single shared instance — import this in your chat route
rag_service = RAGService()