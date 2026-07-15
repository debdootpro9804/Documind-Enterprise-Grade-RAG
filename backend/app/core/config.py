from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "DocuMind"
    app_env: str = "development"
    secret_key: str
    debug: bool = False

    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment_name: str
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_embedding_deployment: str = "text-embedding-3-large"
    azure_embedding_dimensions: int = 3072

    # Groq fallback
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "documind-index"

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    database_url: str

    # Upstash Redis
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str

    # Rate limiting
    rate_limit_per_minute: int = 20

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()