import warnings

import polars as pl

from app.services.analytics_executor import (
    group_comparison,
)


def test_group_comparison_handles_null_dimension_group():
    df = pl.DataFrame(
        {
            "Department": [
                "Sales",
                "Sales",
                "Sales",
                None,
                None,
                None,
            ],
            "Revenue": [
                10.0,
                12.0,
                14.0,
                20.0,
                22.0,
                24.0,
            ],
        }
    )

    with warnings.catch_warnings(
        record=True
    ) as caught:
        warnings.simplefilter(
            "always"
        )

        result = group_comparison(
            df,
            "Revenue",
            "Department",
        )

    comparison_warnings = [
        warning
        for warning in caught
        if (
            "Comparisons with None"
            in str(warning.message)
        )
    ]

    assert comparison_warnings == []

    groups = {
        item["Department"]: item
        for item in result["groups"]
    }

    assert None in groups
    assert groups[None]["count"] == 3
    assert groups[None]["mean"] == 22.0
