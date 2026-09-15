from app.runtime import build_runtime


def test_runtime_defaults_to_the_deterministic_demo(monkeypatch):
    monkeypatch.delenv("FORGE_RUNTIME_MODE", raising=False)

    runtime = build_runtime()

    assert runtime.mode == "demo"
    assert runtime.demo_mode is True
    assert runtime.chunks_count > 23
    assert runtime.ingestion()["mode"] == "demo"


def test_runtime_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("FORGE_RUNTIME_MODE", "staging")

    try:
        build_runtime()
    except RuntimeError as exc:
        assert "demo" in str(exc)
        assert "production" in str(exc)
    else:
        raise AssertionError("build_runtime should reject an unknown runtime mode")
