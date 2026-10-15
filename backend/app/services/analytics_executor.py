from pathlib import Path

from scipy import stats
import polars as pl

from app.security.data_access import load_safe_dataset


def load_dataset(
    file_path: str,
    protected_columns: dict | None = None,
) -> pl.DataFrame:
    path = Path(file_path)

    if protected_columns:
        safe_df = load_safe_dataset(
            file_path,
            protected_columns,
        )

        return pl.from_pandas(safe_df)

    if path.suffix.lower() == ".csv":
        return pl.read_csv(path)

    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pl.read_excel(path)

    raise ValueError("Unsupported file format")


def execute_analysis(
    file_path: str,
    analysis: dict,
    protected_columns: dict | None = None,
) -> dict:

    df = load_dataset(
        file_path,
        protected_columns,
    )

    analysis_type = analysis["type"]

    if analysis_type == "descriptive_statistics":
        return descriptive_statistics(
            df,
            analysis["measure"],
        )

    if analysis_type == "group_comparison":
        return group_comparison(
            df,
            analysis["measure"],
            analysis["dimension"],
        )
    
    if analysis_type == "time_series":
        return time_series(
            df,
            analysis["measure"],
            analysis["date"],
        )

    if analysis_type == "correlation":
        return correlation(
            df,
            analysis["columns"][0],
            analysis["columns"][1],
        )

    raise ValueError(f"Unsupported analysis type: {analysis_type}")


def descriptive_statistics(
    df: pl.DataFrame,
    measure: str,
) -> dict:
    series = df[measure].drop_nulls()

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)

    iqr = q3 - q1

    lower_bound = q1 - (1.5 * iqr)
    upper_bound = q3 + (1.5 * iqr)

    outliers = (
        series
        .filter(
            (series < lower_bound)
            | (series > upper_bound)
        )
        .to_list()
    )

    return {
        "type": "descriptive_statistics",
        "measure": measure,
        "count": series.len(),
        "mean": series.mean(),
        "median": series.median(),
        "min": series.min(),
        "max": series.max(),
        "std": series.std(),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "outlier_lower_bound": lower_bound,
        "outlier_upper_bound": upper_bound,
        "outliers": outliers,
    }



def group_comparison(df, measure, dimension):
    grouped = (
        df
        .group_by(dimension)
        .agg([
            pl.col(measure).count().alias("count"),
            pl.col(measure).mean().alias("mean"),
            pl.col(measure).median().alias("median"),
            pl.col(measure).min().alias("min"),
            pl.col(measure).max().alias("max"),
        ])
        .sort("mean", descending=True)
    )

    groups = grouped.to_dicts()

    group_values = []
    group_sizes = {}

    for group in groups:
        group_name = group[dimension]

        group_filter = (
            pl.col(dimension).is_null()
            if group_name is None
            else pl.col(dimension) == group_name
        )

        values = (
            df
            .filter(group_filter)
            .select(measure)
            .drop_nulls()
            .to_series()
            .to_list()
        )

        group_sizes[str(group_name)] = len(values)

        if len(values) >= 2:
            group_values.append(values)

    statistical_test = None

    if any(size < 3 for size in group_sizes.values()):
        statistical_test = {
            "test": "one_way_anova",
            "status": "insufficient_data",
            "reason": "Each group must contain at least three observations.",
            "group_sizes": group_sizes,
            "minimum_group_size": 3,
        }

    elif len(group_values) >= 2:
        statistic, p_value = stats.f_oneway(*group_values)

        p_value = float(p_value)

        statistical_test = {
            "test": "one_way_anova",
            "statistic": float(statistic),
            "p_value": p_value,
            "p_value_underflow": p_value == 0.0,
            "sample_size": sum(
                len(values)
                for values in group_values
            ),
            "group_count": len(group_values),
        }

    return {
        "type": "group_comparison",
        "measure": measure,
        "dimension": dimension,
        "groups": groups,
        "statistical_test": statistical_test,
    }

def time_series(df, measure, date):
    series_df = (
        df
        .select([date, measure])
        .drop_nulls()
        .sort(date)
    )

    return {
        "type": "time_series",
        "measure": measure,
        "date": date,
        "data": series_df.to_dicts(),
        "sample_size": series_df.height,
        "method": "sorted_time_series",
    }

def _build_scatter_visualization(
    first,
    second,
    x,
    y,
    max_points=200,
):
    """
    Build deterministic scatter-plot data from the same paired
    observations used by Pearson correlation.

    Large datasets are reduced deterministically so the API does
    not send thousands of points to the browser.
    """
    total_points = len(x)

    if total_points == 0:
        indices = []
    elif total_points <= max_points:
        indices = list(range(total_points))
    else:
        indices = [
            round(
                index
                * (total_points - 1)
                / (max_points - 1)
            )
            for index in range(max_points)
        ]

    points = [
        {
            "x": x[index],
            "y": y[index],
        }
        for index in indices
    ]

    return {
        "type": "scatter",
        "x_column": first,
        "y_column": second,
        "points": points,
        "total_points": total_points,
        "displayed_points": len(points),
        "sampled": (
            total_points > max_points
        ),
    }

def correlation(df, first, second):
    pair = (
        df
        .select([first, second])
        .drop_nulls()
    )

    x = pair[first].to_list()
    y = pair[second].to_list()

    sample_size = pair.height

    if sample_size < 2:
        return {
            "type": "correlation",
            "columns": [first, second],
            "correlation": None,
            "p_value": None,
            "sample_size": sample_size,
            "method": "pearson_correlation",
            "status": "insufficient_data",
            "reason": (
                "Pearson correlation requires at least two "
                "paired observations."
            ),
        }

    if len(set(x)) < 2 or len(set(y)) < 2:
        return {
            "type": "correlation",
            "columns": [first, second],
            "correlation": None,
            "p_value": None,
            "sample_size": sample_size,
            "method": "pearson_correlation",
            "status": "insufficient_variation",
            "reason": (
                "Pearson correlation requires variation "
                "in both columns."
            ),
        }

    correlation_value, p_value = stats.pearsonr(x, y)

    return {
        "type": "correlation",
        "columns": [first, second],
        "correlation": float(correlation_value),
        "p_value": float(p_value),
        "sample_size": sample_size,
        "method": "pearson_correlation",
        "status": "completed",
        "visualization": _build_scatter_visualization(
            first,
            second,
            x,
            y,
        ),
    }
