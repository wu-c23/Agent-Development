import json

from safe_search import Book, SafeSearchEngine


def main() -> None:
    engine = SafeSearchEngine()

    books = [
        Book(
            id="1",
            title="Mystery of the Old City",
            intro="A detective explores a city of secrets with a calm lead.",
            tags=["mystery", "adventure"],
            status="completed",
            sentiment_summary="Praised for pacing, low angst.",
        ),
        Book(
            id="2",
            title="Fallen Empire",
            intro="A dark epic with a suffering protagonist and many twists.",
            tags=["angst", "epic"],
            status="ongoing",
            sentiment_summary="Readers warn about heavy angst.",
        ),
    ]

    engine.index_books(books)

    result = engine.search(
        query="I want something like a mystery epic but with a lighter mood",
        avoid_tags=["angst"],
        top_k=5,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
