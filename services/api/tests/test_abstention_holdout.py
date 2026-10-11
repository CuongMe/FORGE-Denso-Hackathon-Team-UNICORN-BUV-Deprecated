import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from app.evaluation import DATASETS, EvaluationRequest


HOLDOUT_PATH = Path(__file__).resolve().parents[3] / "data" / "evaluation" / "abstention_holdout_v1.jsonl"


def test_abstention_holdout_contains_only_unanswerable_cases():
    cases = [json.loads(line) for line in HOLDOUT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(cases) == 4
    assert all(case["answerable"] is False for case in cases)
    assert all(case["question_type"] == "abstention" for case in cases)
    assert all(not case["gold_evidence"] for case in cases)


def test_evaluator_only_accepts_the_four_case_holdout():
    assert list(DATASETS) == ["abstention"]
    assert EvaluationRequest().limit == 4
    with pytest.raises(ValidationError):
        EvaluationRequest(dataset="golden")
    with pytest.raises(ValidationError):
        EvaluationRequest(limit=5)
