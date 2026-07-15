from loguru import logger
from openai import AsyncAzureOpenAI, APIError, APITimeoutError
from groq import AsyncGroq
from typing import AsyncGenerator
from app.core.config import settings


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


# Singleton — import this everywhere
llm_service = LLMService()