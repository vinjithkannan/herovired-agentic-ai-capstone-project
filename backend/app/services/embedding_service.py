
import os
import httpx

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://ollama:11434"
)

EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "nomic-embed-text"
)

EMBEDDING_DIMENSION = int(
    os.getenv("EMBEDDING_DIMENSION", "768")
)

BATCH_SIZE = 32


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings using the configured local provider.
    Returns one vector per input text.
    """

    if not texts:
        return []

    if EMBEDDING_PROVIDER != "ollama":
        raise ValueError(
            f"Unsupported embedding provider: {EMBEDDING_PROVIDER}"
        )

    embeddings = []

    with httpx.Client(timeout=120.0) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]

            response = client.post(
                f"{OLLAMA_BASE_URL}/api/embed",
                json={
                    "model": EMBEDDING_MODEL,
                    "input": batch
                }
            )

            response.raise_for_status()

            result = response.json()
            batch_embeddings = result["embeddings"]

            if len(batch_embeddings) != len(batch):
                raise ValueError(
                    "Embedding count does not match input count"
                )

            for vector in batch_embeddings:
                if len(vector) != EMBEDDING_DIMENSION:
                    raise ValueError(
                        f"Expected {EMBEDDING_DIMENSION} dimensions, "
                        f"received {len(vector)}"
                    )

            embeddings.extend(batch_embeddings)

    return embeddings
