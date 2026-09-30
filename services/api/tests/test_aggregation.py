from app.aggregation import aggregate_rows


def test_count_aggregation_filters_matching_table_values():
    result = aggregate_rows(
        "From the industrial data set, how many routine checks were conducted?",
        [
            {"Activity": "Routine check", "Machine": "A"},
            {"Activity": "Repair", "Machine": "A"},
            {"Activity": "Routine check", "Machine": "B"},
        ],
        source_doc_id="doc-1",
        source_name="industrial_dataset.csv",
    )

    assert result is not None
    assert result.summary.operation == "count"
    assert result.summary.value == 2
    assert result.summary.rows_matched == 2


def test_average_aggregation_selects_numeric_column():
    result = aggregate_rows(
        "What is the average temperature?",
        [{"Temperature": "20"}, {"Temperature": "30"}],
        source_doc_id="doc-1",
        source_name="measurements.csv",
    )

    assert result is not None
    assert result.summary.operation == "average"
    assert result.summary.value == 25
    assert result.summary.column == "Temperature"


def test_unsupported_question_returns_no_aggregation():
    assert aggregate_rows(
        "Explain the maintenance procedure.",
        [{"Activity": "Routine check"}],
        source_doc_id="doc-1",
        source_name="data.csv",
    ) is None
