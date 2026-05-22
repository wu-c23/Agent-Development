from typing import List

import chromadb

from .config import CHROMA_PATH, COLLECTION_NAME
from .models import Book


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_books(collection, books: List[Book], embeddings: List[List[float]]) -> None:
    collection.upsert(
        ids=[book.id for book in books],
        embeddings=embeddings,
        documents=[book.intro for book in books],
        metadatas=[
            {
                "title": book.title,
                "tags": ",".join(book.tags),
                "status": book.status or "",
                "sentiment_summary": book.sentiment_summary or "",
            }
            for book in books
        ],
    )
