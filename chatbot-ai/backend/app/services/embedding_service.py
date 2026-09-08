from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import settings


@lru_cache
def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds a batch of texts with the configured OpenAI model. Tests
    monkeypatch this function to avoid real API calls."""

    if not texts:
        return []
    response = await _client().embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=texts,
        dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
    )
    return [item.embedding for item in response.data]


async def embed_query(text: str) -> list[float]:
    vectors = await embed_texts([text])
    return vectors[0]
