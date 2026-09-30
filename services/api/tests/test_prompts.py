from app.prompts import GROUNDED_PROMPT_VERSION, grounded_system_prompt


def test_grounded_prompt_is_versioned_and_contains_safety_rules():
    prompt = grounded_system_prompt()

    assert GROUNDED_PROMPT_VERSION
    assert "Answer only from the supplied evidence." in prompt
    assert "ABSTAIN" in prompt
