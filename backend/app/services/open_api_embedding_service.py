from openai import OpenAI
from app.core.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env and restart the backend.")
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _client()
    # Batch conservatively to avoid oversized requests.
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), 64):
        batch = texts[offset:offset + 64]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors
