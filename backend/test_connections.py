import asyncio
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
from pinecone import Pinecone
from upstash_redis import Redis
from openai import AsyncAzureOpenAI
from groq import AsyncGroq
from app.core.config import settings


async def test_supabase():
    print("\n--- Testing Supabase ---")
    try:
        
        sb = create_client(settings.supabase_url, settings.supabase_service_key)
        # Try reading from documents table (will be empty, that's fine)
        result = sb.table("documents").select("id").limit(1).execute()
        print("✓ Supabase connected. Documents table exists.")
    except Exception as e:
        print(f"✗ Supabase failed: {e}")


async def test_pinecone():
    print("\n--- Testing Pinecone ---")
    try:
        
        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index_name)
        stats = index.describe_index_stats()
        print(f"✓ Pinecone connected. Index dimension: {stats.dimension}, vectors stored: {stats.total_vector_count}")
    except Exception as e:
        print(f"✗ Pinecone failed: {e}")


async def test_upstash():
    print("\n--- Testing Upstash Redis ---")
    try:
        
        redis = Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
        )
        redis.set("documind_test", "hello")
        value = redis.get("documind_test")
        redis.delete("documind_test")
        print(f"✓ Upstash Redis connected. Test value round-trip: '{value}'")
    except Exception as e:
        print(f"✗ Upstash failed: {e}")


async def test_azure_openai():
    print("\n--- Testing Azure OpenAI ---")
    try:
        
        client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        response = await client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[{"role": "user", "content": "Say hello in 3 words."}],
            max_tokens=10,
        )
        reply = response.choices[0].message.content
        print(f"✓ Azure OpenAI connected. Reply: '{reply}'")
    except Exception as e:
        print(f"✗ Azure OpenAI failed: {e}")


async def test_groq():
    print("\n--- Testing Groq ---")
    try:
        
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": "Say hello in 3 words."}],
            max_tokens=10,
        )
        reply = response.choices[0].message.content
        print(f"✓ Groq connected. Reply: '{reply}'")
    except Exception as e:
        print(f"✗ Groq failed: {e}")


async def test_embedding():
    print("\n--- Testing Embedding model ---")
    try:
        
        client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        response = await client.embeddings.create(
            input="This is a test sentence.",
            model=settings.azure_embedding_deployment,
            dimensions=settings.azure_embedding_dimensions,
        )
        vec = response.data[0].embedding
        print(f"✓ Embedding model working. Vector length: {len(vec)} (should be 3072)")
    except Exception as e:
        print(f"✗ Embedding failed: {e}")


async def main():
    print("=" * 50)
    print("  DocuMind — connection test")
    print("=" * 50)
    await test_supabase()
    await test_pinecone()
    await test_upstash()
    await test_azure_openai()
    await test_groq()
    await test_embedding()
    print("\n" + "=" * 50)
    print("  Done. Fix any ✗ before continuing.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())