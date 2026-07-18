from loguru import logger
from openai import AsyncAzureOpenAI, APIError, APITimeoutError
from groq import AsyncGroq
from typing import AsyncGenerator
from app.core.config import settings
import base64

class LLMService:
    """
    Primary: Azure OpenAI
    Fallback: Groq (Llama 3.3 70B) — automatic, no user sees the switch
    """

    def __init__(self):
        self.azure_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        self.groq_client = AsyncGroq(api_key=settings.groq_api_key)

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens. Try Azure first, silently fall back to Groq."""
        try:
            async for chunk in self._azure_stream(messages, temperature):
                yield chunk
        except (APIError, APITimeoutError, Exception) as e:
            logger.warning(f"Azure OpenAI failed ({type(e).__name__}), switching to Groq fallback")
            async for chunk in self._groq_stream(messages, temperature):
                yield chunk

    async def _azure_stream(
        self, messages: list[dict], temperature: float
    ) -> AsyncGenerator[str, None]:
        stream = await self.azure_client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def _groq_stream(
        self, messages: list[dict], temperature: float
    ) -> AsyncGenerator[str, None]:
        stream = await self.groq_client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def get_embedding(self, text: str) -> list[float]:
        """Embeddings always via Azure (no Groq fallback needed here)."""
        response = await self.azure_client.embeddings.create(
            input=text,
            model=settings.azure_embedding_deployment,
            dimensions=settings.azure_embedding_dimensions
        )
        return response.data[0].embedding
    
    async def describe_image(self, image_bytes: bytes, image_ext: str) -> str:
        """
        Send an image to model and get a text description back.
        This description is then embedded and stored in Pinecone like any text chunk.

        image_ext should be 'jpeg', 'png', or 'webp' — the MIME subtype.
        """

         # Encode image to base64 — required by the OpenAI vision API
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        media_type = f"image/{image_ext}"

        prompt = (
        "You are analyzing an image from a document. "
        "Describe everything you see in detail — text, charts, tables, diagrams, "
        "figures, logos, or any visual content. "
        "If there is a chart or graph, describe the data it shows including any values, "
        "trends, labels, and axes. "
        "If there is a table, describe its structure and content. "
        "Your description will be used to answer questions about this document, "
        "so be thorough and precise. "
        "Start directly with the description, no preamble."
        )

        try:
            response = await self.azure_client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
            description = response.choices[0].message.content
            logger.info(f"Vision description generated ({len(description)} chars)")
            return description

        except Exception as e:
            logger.warning(f"Vision description failed: {e} — using placeholder")
            return "Image could not be processed."



# Singleton — import this everywhere
llm_service = LLMService()