from __future__ import annotations

from app.corpus import load_source_pack_chunks
from app.production import ProductionHybridRetriever, ProductionSettings


def main() -> None:
    settings = ProductionSettings.from_env()
    retriever = ProductionHybridRetriever(settings)
    count = retriever.upsert_chunks(load_source_pack_chunks())
    print(
        f"Indexed {count} chunks into Qdrant collection "
        f"'{settings.collection_name}' using {settings.dense_model} + {settings.sparse_model}."
    )


if __name__ == "__main__":
    main()
