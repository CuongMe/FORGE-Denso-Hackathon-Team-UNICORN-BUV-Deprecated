from __future__ import annotations

from app.corpus import load_source_pack_chunks
from app.corpus import list_demo_documents
from app.persistence import LifecycleStore
from app.production import ProductionHybridRetriever, ProductionSettings


def index_source_pack(
    *,
    retriever: ProductionHybridRetriever | None = None,
    store: LifecycleStore | None = None,
) -> tuple[int, LifecycleStore, ProductionSettings]:
    settings = ProductionSettings.from_env()
    active_retriever = retriever or ProductionHybridRetriever(settings)
    active_store = store or LifecycleStore()
    active_store.initialize()
    chunks = load_source_pack_chunks()
    summaries = list_demo_documents(chunks)
    active_store.sync_documents(summaries)
    count = active_retriever.upsert_chunks(chunks)
    for summary in summaries:
        existing = active_store.get_document(str(summary['doc_id'])) or {}
        active_store.upsert_document(
            summary,
            content_hash=str(existing.get('content_hash') or ''),
            size_bytes=int(existing.get('size_bytes') or 0),
            status='indexed',
            index_version='',
        )
    corpus_version = active_store.indexed_corpus_version()
    for summary in summaries:
        existing = active_store.get_document(str(summary['doc_id'])) or {}
        active_store.upsert_document(
            summary,
            content_hash=str(existing.get('content_hash') or ''),
            size_bytes=int(existing.get('size_bytes') or 0),
            status='indexed',
            index_version=corpus_version,
        )
    indexed_documents, indexed_chunks = active_store.indexed_counts()
    active_store.set_index_snapshot(
        collection_name=settings.collection_name,
        corpus_version=active_store.indexed_corpus_version(),
        indexed_documents=indexed_documents,
        indexed_chunks=indexed_chunks,
    )
    return count, active_store, settings


def main() -> None:
    count, _, settings = index_source_pack()
    print(
        f"Indexed {count} chunks into Qdrant collection "
        f"'{settings.collection_name}' using {settings.dense_model} + {settings.sparse_model}."
    )


if __name__ == "__main__":
    main()
