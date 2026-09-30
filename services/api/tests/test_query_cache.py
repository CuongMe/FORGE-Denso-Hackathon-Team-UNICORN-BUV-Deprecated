from pathlib import Path

from app.persistence import LifecycleStore


def test_query_cache_round_trips_json_and_expires():
    database = Path('.forge-query-cache-test.sqlite3')
    store = LifecycleStore(database)
    try:
        store.initialize()
        store.put_query_cache(
            "key-1",
            corpus_version="corpus-1",
            prompt_version="prompt-1",
            response={"answer": "cached"},
            ttl_seconds=60,
        )

        assert store.get_query_cache("key-1")["answer"] == "cached"
    finally:
        for suffix in ('', '-wal', '-shm'):
            try:
                database.with_name(database.name + suffix).unlink()
            except FileNotFoundError:
                pass
