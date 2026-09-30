from app.query_router import classify_query


def test_routes_tabular_count_to_aggregation():
    route = classify_query(
        "From the industrial data set, how many routine checks were conducted?",
        tabular_available=True,
    )

    assert route.kind == "aggregation"


def test_routes_image_explanation_to_visual():
    route = classify_query("Explain this image and identify the defect.")

    assert route.kind == "visual"


def test_routes_normal_question_to_rag():
    route = classify_query("What is the safety procedure for restarting the line?")

    assert route.kind == "rag"


def test_does_not_aggregate_without_tabular_evidence():
    route = classify_query("How many routine checks were conducted?", tabular_available=False)

    assert route.kind == "rag"
