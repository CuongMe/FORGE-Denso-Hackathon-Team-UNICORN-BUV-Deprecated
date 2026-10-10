import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = PROJECT_ROOT / "data" / "evaluation" / "golden_dataset_v1.jsonl"
ACTIVE_DATASET_PATH = PROJECT_ROOT / "data" / "evaluation" / "golden_dataset_v2_en.jsonl"
ABSTENTION_HOLDOUT_PATH = PROJECT_ROOT / "data" / "evaluation" / "abstention_holdout_v1.jsonl"
REVIEW_LOG_PATH = PROJECT_ROOT / "data" / "evaluation" / "human_review_log.csv"


def _cases() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _active_cases() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in ACTIVE_DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_golden_dataset_has_expected_coverage_and_unique_ids():
    cases = _cases()
    ids = [case["case_id"] for case in cases]

    assert len(cases) == 30
    assert len(set(ids)) == len(ids)
    assert all(bool(case["answerable"]) for case in cases)
    assert sum(bool(case["answerable"]) for case in cases) == 30
    assert sum(not bool(case["answerable"]) for case in cases) == 0
    assert {case["question_type"] for case in cases} >= {
        "visual_ocr_numeric",
        "spreadsheet_aggregation",
        "bilingual_retrieval",
        "spreadsheet_derived_ranking",
        "cross_document_reasoning",
        "csv_row_lookup",
    }


def test_active_golden_dataset_is_new_english_set_covering_current_corpus():
    cases = _active_cases()
    archived_questions = {case["question"].casefold() for case in _cases()}

    assert len(cases) == 34
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert len({case["question"].casefold() for case in cases}) == len(cases)
    assert all(case["language"] == "en" and case["answerable"] for case in cases)
    assert not archived_questions.intersection(case["question"].casefold() for case in cases)
    assert len({item["doc_id"] for case in cases for item in case["gold_evidence"]}) == 17
    assert "spreadsheet_aggregation" in {case["question_type"] for case in cases}
    source_extensions = {Path(item["source_path"]).suffix for case in cases for item in case["gold_evidence"]}
    assert {".pdf", ".png", ".xlsx", ".csv"} <= source_extensions


def test_golden_dataset_evidence_and_answerability_contract_is_valid():
    cases = _cases() + _active_cases()

    for case in cases:
        evidence = case["gold_evidence"]
        assert isinstance(evidence, list)
        assert bool(case["answerable"]) == bool(evidence)
        assert case["verification_status"].endswith("pending_human_signoff")

        for item in evidence:
            source_path = PROJECT_ROOT / item["source_path"]
            assert source_path.is_file(), source_path
            assert item["doc_id"]
            assert item["chunk_id"]
            assert item["quote"]
            assert item["region"]

        if not case["answerable"]:
            assert case["reference_answer"].startswith("I don't know")
            assert case["required_facts"] == []


def test_human_review_log_covers_every_case():
    cases = _cases() + [
        json.loads(line)
        for line in ABSTENTION_HOLDOUT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] + _active_cases()
    with REVIEW_LOG_PATH.open(encoding="utf-8", newline="") as stream:
        review_rows = list(csv.DictReader(stream))

    assert [row["case_id"] for row in review_rows] == [case["case_id"] for case in cases]
    assert all(row["review_status"] in {"pending_human_signoff", "signed_off"} for row in review_rows)
    assert all(not row["reviewer"] and not row["reviewed_at"] for row in review_rows if row["review_status"] == "pending_human_signoff")


def test_abstention_holdout_remains_separate_from_answerable_dataset():
    holdout = [
        json.loads(line)
        for line in ABSTENTION_HOLDOUT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert [case["case_id"] for case in holdout] == ["G035", "G036", "G037", "G038"]
    assert all(case["answerable"] is False for case in holdout)
    assert all(case["question_type"] == "abstention" for case in holdout)
