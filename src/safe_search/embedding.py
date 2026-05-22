from typing import List

from openai import OpenAI

from .config import API_KEY, EMBEDDING_MODEL


def embed_texts(client: OpenAI, texts: List[str]) -> List[List[float]]:
    if not API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]
