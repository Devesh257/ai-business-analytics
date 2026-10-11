import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  analyzeDataset,
  downloadAnalysisRunExport,
  loadAnalysisRun,
  loadAnalysisRuns,
  listOwnedDatasets,
  loadDatasetOverview,
  loadDatasetPlan,
  uploadDataset,
} from "./api";

import DatasetLibrary from "./DatasetLibrary.jsx";

const supportedExtensions = ["csv", "xlsx", "xls"];


function formatValue(value) {
  if (value === null || value === undefined) {
    return "Not available";
  }

  if (Array.isArray(value)) {
    return value.join(", ");
  }

  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value.toString()
      : value.toPrecision(5);
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function sampleSeriesPoints(
  data,
  maxPoints = 240,
) {
  if (!Array.isArray(data)) {
    return [];
  }

  if (data.length <= maxPoints) {
    return data;
  }

  return Array.from(
    {
      length: maxPoints,
    },
    (_, index) => {
      const sourceIndex = Math.round(
        index *
          (data.length - 1) /
          (maxPoints - 1)
      );

      return data[sourceIndex];
    }
  );
}


function formatChartDate(value) {
  if (
    value === null ||
    value === undefined
  ) {
    return "Unknown";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return String(value);
  }

  return date.toLocaleDateString(
    undefined,
    {
      year: "numeric",
      month: "short",
      day: "numeric",
    }
  );
}

function StatusPill({
  tone = "neutral",
  children,
}) {
  return (
    <span className={`pill ${tone}`}>
      {children}
    </span>
  );
}


function TrustPanel() {
  return (
    <aside className="trust-panel">
      <p className="eyebrow">
        Trust by design
      </p>

      <h2>
        Evidence first. AI second.
      </h2>

      <ul>
        <li>
          <span>01</span>
          Numbers come from deterministic analysis.
        </li>

        <li>
          <span>02</span>
          Only verified insights reach this dashboard.
        </li>

        <li>
          <span>03</span>
          AI explains approved evidence; it does not calculate it.
        </li>
      </ul>
    </aside>
  );
}


function DatasetOverview({
  upload,
  overview,
}) {
  const semanticColumns = Object.entries(
    overview.semantics?.columns ?? {}
  );

  const protectedColumns = Object.entries(
    overview.pii?.protected_columns ?? {}
  );

  return (
    <section className="overview card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            Dataset overview
          </p>

          <h2>
            {upload.file_name}
          </h2>
        </div>

        <StatusPill
          tone={
            overview.validation.valid
              ? "success"
              : "danger"
          }
        >
          {overview.validation.valid
            ? "Validated"
            : "Validation needs attention"}
        </StatusPill>
      </div>

      <div className="stats-grid">
        <div>
          <strong>
            {overview.validation.rows}
          </strong>

          <span>
            Rows
          </span>
        </div>

        <div>
          <strong>
            {overview.validation.columns}
          </strong>

          <span>
            Columns
          </span>
        </div>

        <div>
          <strong>
            {semanticColumns.length}
          </strong>

          <span>
            Safe columns profiled
          </span>
        </div>
      </div>

      {overview.validation.warnings?.length > 0 && (
        <div className="notice warning">
          <strong>
            Data quality notes
          </strong>

          <span>
            {overview.validation.warnings.join(" ")}
          </span>
        </div>
      )}

      {protectedColumns.length > 0 ? (
        <div className="notice protected">
          <strong>
            PII gate active
          </strong>

          <span>
            {protectedColumns
              .map(
                ([column, type]) =>
                  `${column} (${type})`
              )
              .join(", ")}{" "}
            will be excluded from profiling and analysis.
          </span>
        </div>
      ) : (
        <div className="notice success">
          <strong>
            PII scan complete
          </strong>

          <span>
            No protected columns were detected.
          </span>
        </div>
      )}

      <div className="role-list">
        <h3>
          Detected semantic roles
        </h3>

        {semanticColumns.length ? (
          semanticColumns.map(
            ([name, detail]) => (
              <div
                className="role-row"
                key={name}
              >
                <span>
                  {name}
                </span>

                <StatusPill>
                  {detail.role}
                </StatusPill>

                <small>
                  {detail.dtype} ·{" "}
                  {detail.unique_count} unique
                </small>
              </div>
            )
          )
        ) : (
          <p className="muted">
            No safe columns are available for semantic analysis.
          </p>
        )}
      </div>
    </section>
  );
}


function PlanSummary({
  plan,
}) {
  if (!plan) {
    return null;
  }

  const analyses = plan.analyses ?? [];

  const counts = analyses.reduce(
    (result, analysis) => {
      const type = analysis.type;

      result[type] =
        (result[type] ?? 0) + 1;

      return result;
    },
    {}
  );

  return (
    <section className="card plan-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            Deterministic analysis plan
          </p>

          <h2>
            {analyses.length} analyses prepared
          </h2>
        </div>

        <StatusPill tone="success">
          Planner ready
        </StatusPill>
      </div>

      <div className="plan-stats">
        <div>
          <strong>
            {counts.descriptive_statistics ?? 0}
          </strong>

          <span>
            Descriptive
          </span>
        </div>

        <div>
          <strong>
            {counts.group_comparison ?? 0}
          </strong>

          <span>
            Group comparisons
          </span>
        </div>

        <div>
          <strong>
            {counts.correlation ?? 0}
          </strong>

          <span>
            Correlations
          </span>
        </div>

        <div>
          <strong>
            {counts.time_series ?? 0}
          </strong>

          <span>
            Time series
          </span>
        </div>
      </div>

      <div className="plan-columns">
        <div>
          <h3>
            Measures
          </h3>

          <p>
            {plan.measures?.length
              ? plan.measures.join(", ")
              : "None"}
          </p>
        </div>

        <div>
          <h3>
            Dimensions
          </h3>

          <p>
            {plan.dimensions?.length
              ? plan.dimensions.join(", ")
              : "None"}
          </p>
        </div>

        <div>
          <h3>
            Dates
          </h3>

          <p>
            {plan.dates?.length
              ? plan.dates.join(", ")
              : "None"}
          </p>
        </div>

        <div>
          <h3>
            Identifiers excluded
          </h3>

          <p>
            {plan.identifiers?.length
              ? plan.identifiers.join(", ")
              : "None"}
          </p>
        </div>
      </div>
    </section>
  );
}


function getRunInsightKey(
  insight
) {
  return [
    insight?.insight_type ?? "",
    insight?.method ?? "",
    ...(insight?.source_columns ?? []),
  ].join("::");
}


function getRunConfidenceCounts(
  insights
) {
  return insights.reduce(
    (counts, insight) => {
      const level =
        insight?.confidence
          ?.level?.toLowerCase();

      if (
        level === "high" ||
        level === "medium" ||
        level === "low"
      ) {
        counts[level] += 1;
      }

      return counts;
    },
    {
      high: 0,
      medium: 0,
      low: 0,
    }
  );
}


function summarizePersistedRun(
  run
) {
  const insights =
    run?.ranked_insights ?? [];

  return {
    verifiedSignals:
      insights.length,
    confidence:
      getRunConfidenceCounts(
        insights
      ),
    topInsight:
      insights[0] ?? null,
  };
}


function comparePersistedRuns(
  firstRun,
  secondRun
) {
  const ordered = [
    firstRun,
    secondRun,
  ].sort(
    (left, right) => {
      const leftTime =
        new Date(
          left?.created_at ?? 0
        ).getTime();

      const rightTime =
        new Date(
          right?.created_at ?? 0
        ).getTime();

      if (leftTime !== rightTime) {
        return leftTime - rightTime;
      }

      return String(
        left?.id ?? ""
      ).localeCompare(
        String(
          right?.id ?? ""
        )
      );
    }
  );

  const baseline = ordered[0];
  const current = ordered[1];

  const baselineInsights =
    baseline?.ranked_insights ?? [];

  const currentInsights =
    current?.ranked_insights ?? [];

  const baselineMap =
    new Map(
      baselineInsights.map(
        (insight) => [
          getRunInsightKey(
            insight
          ),
          insight,
        ]
      )
    );

  const currentMap =
    new Map(
      currentInsights.map(
        (insight) => [
          getRunInsightKey(
            insight
          ),
          insight,
        ]
      )
    );

  const added = [];
  const removed = [];
  const changed = [];

  currentMap.forEach(
    (insight, key) => {
      if (
        !baselineMap.has(key)
      ) {
        added.push(insight);
        return;
      }

      const previous =
        baselineMap.get(key);

      const previousScore =
        typeof previous?.score ===
          "number"
          ? previous.score
          : null;

      const currentScore =
        typeof insight?.score ===
          "number"
          ? insight.score
          : null;

      const previousConfidence =
        previous?.confidence
          ?.score;

      const currentConfidence =
        insight?.confidence
          ?.score;

      const scoreChanged =
        previousScore !== null &&
        currentScore !== null &&
        Math.abs(
          currentScore -
          previousScore
        ) > 1e-9;

      const confidenceChanged =
        typeof previousConfidence ===
          "number" &&
        typeof currentConfidence ===
          "number" &&
        Math.abs(
          currentConfidence -
          previousConfidence
        ) > 1e-9;

      const levelChanged =
        previous?.confidence
          ?.level !==
        insight?.confidence
          ?.level;

      const titleChanged =
        previous?.title !==
        insight?.title;

      if (
        scoreChanged ||
        confidenceChanged ||
        levelChanged ||
        titleChanged
      ) {
        changed.push({
          before: previous,
          after: insight,
          scoreDelta:
            previousScore !== null &&
            currentScore !== null
              ? currentScore -
                previousScore
              : null,
          confidenceDelta:
            typeof previousConfidence ===
              "number" &&
            typeof currentConfidence ===
              "number"
              ? currentConfidence -
                previousConfidence
              : null,
        });
      }
    }
  );

  baselineMap.forEach(
    (insight, key) => {
      if (
        !currentMap.has(key)
      ) {
        removed.push(insight);
      }
    }
  );

  return {
    baseline,
    current,
    baselineSummary:
      summarizePersistedRun(
        baseline
      ),
    currentSummary:
      summarizePersistedRun(
        current
      ),
    added,
    removed,
    changed,
  };
}


function RunChangeList({
  title,
  description,
  items,
  type,
}) {
  return (
    <div className="run-change-panel">
      <div className="run-change-heading">
        <strong>
          {title}
        </strong>

        <span>
          {description}
        </span>
      </div>

      {items.length ? (
        <div className="run-change-items">
          {items.map(
            (
              item,
              index
            ) => {
              const insight =
                type === "changed"
                  ? item.after
                  : item;

              return (
                <div
                  className="run-change-item"
                  key={
                    `${getRunInsightKey(
                      insight
                    )}-${index}`
                  }
                >
                  <strong>
                    {insight.title}
                  </strong>

                  <span>
                    {insight
                      .confidence
                      ?.level ??
                      "Confidence unavailable"}

                    {type ===
                      "changed" &&
                    typeof item
                      .scoreDelta ===
                      "number"
                      ? (
                        ` · score ${
                          item.scoreDelta >
                          0
                            ? "+"
                            : ""
                        }${formatValue(
                          item.scoreDelta
                        )}`
                      )
                      : ""}
                  </span>
                </div>
              );
            }
          )}
        </div>
      ) : (
        <p className="run-change-empty">
          None detected.
        </p>
      )}
    </div>
  );
}


function AnalysisRunHistory({
  history,
  currentRunId,
}) {
  const runs =
    history?.analysis_runs ?? [];

  const [
    selectedRunIds,
    setSelectedRunIds,
  ] = useState([]);

  const [
    comparison,
    setComparison,
  ] = useState(null);

  const [
    comparisonState,
    setComparisonState,
  ] = useState("idle");

  const [
    comparisonError,
    setComparisonError,
  ] = useState("");

  const [
    viewedRun,
    setViewedRun,
  ] = useState(null);

  const [
    viewState,
    setViewState,
  ] = useState("idle");

  if (!runs.length) {
    return null;
  }

  function toggleRunSelection(
    runId
  ) {
    setComparison(null);
    setComparisonError("");

    setSelectedRunIds(
      (current) => {
        if (
          current.includes(runId)
        ) {
          return current.filter(
            (id) => id !== runId
          );
        }

        if (
          current.length >= 2
        ) {
          return current;
        }

        return [
          ...current,
          runId,
        ];
      }
    );
  }

  async function handleViewRun(
    runId
  ) {
    setViewState("loading");

    try {
      const run =
        await loadAnalysisRun(
          runId
        );

      setViewedRun(run);
      setViewState("ready");
    } catch {
      setViewedRun(null);
      setViewState("failed");
    }
  }

  async function handleCompareRuns() {
    if (
      selectedRunIds.length !== 2
    ) {
      return;
    }

    setComparisonState(
      "loading"
    );

    setComparisonError("");

    try {
      const [
        first,
        second,
      ] = await Promise.all(
        selectedRunIds.map(
          (runId) =>
            loadAnalysisRun(
              runId
            )
        )
      );

      setComparison(
        comparePersistedRuns(
          first,
          second
        )
      );

      setComparisonState(
        "ready"
      );
    } catch {
      setComparison(null);

      setComparisonState(
        "failed"
      );

      setComparisonError(
        "The selected runs could not be loaded for comparison."
      );
    }
  }

  const viewedSummary =
    viewedRun
      ? summarizePersistedRun(
          viewedRun
        )
      : null;

  return (
    <section className="card run-history">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            Analysis history
          </p>

          <h2>
            Previous runs
          </h2>

          <p>
            Review persisted runs or
            select any two from this
            dataset version for a
            deterministic comparison.
          </p>
        </div>

        <StatusPill>
          {history.count ??
            runs.length}
          {" total"}
        </StatusPill>
      </div>

      <div className="run-list">
        {runs.map((run) => {
          const selected =
            selectedRunIds.includes(
              run.id
            );

          const isCurrent =
            run.id ===
            currentRunId;

          return (
            <div
              className={
                `run-row` +
                (
                  selected
                    ? " selected"
                    : ""
                )
              }
              key={run.id}
            >
              <button
                className="run-view-button"
                type="button"
                onClick={() =>
                  handleViewRun(
                    run.id
                  )
                }
              >
                <div>
                  <strong>
                    {run.id}
                  </strong>

                  <small>
                    {run.created_at
                      ? new Date(
                          run.created_at
                        ).toLocaleString()
                      : "Time unavailable"}
                  </small>
                </div>

                {isCurrent && (
                  <span className="run-current-label">
                    Current
                  </span>
                )}
              </button>

              <div className="run-row-actions">
                <StatusPill
                  tone={
                    run.status ===
                    "completed"
                      ? "success"
                      : run.status ===
                          "partially_completed"
                        ? "warning"
                        : "danger"
                  }
                >
                  {run.status
                    ?.replaceAll(
                      "_",
                      " "
                    )}
                </StatusPill>

                <label
                  className={
                    `run-compare-choice` +
                    (
                      selected
                        ? " selected"
                        : ""
                    )
                  }
                >
                  <input
                    type="checkbox"
                    checked={
                      selected
                    }
                    disabled={
                      !selected &&
                      selectedRunIds
                        .length >= 2
                    }
                    onChange={() =>
                      toggleRunSelection(
                        run.id
                      )
                    }
                  />

                  Compare
                </label>
              </div>
            </div>
          );
        })}
      </div>

      <div className="run-compare-toolbar">
        <span>
          {
            selectedRunIds.length
          }
          {" of 2 runs selected"}
        </span>

        <div>
          <button
            className="secondary-button"
            type="button"
            disabled={
              selectedRunIds.length !==
                2 ||
              comparisonState ===
                "loading"
            }
            onClick={
              handleCompareRuns
            }
          >
            {comparisonState ===
            "loading"
              ? "Comparing…"
              : "Compare selected runs"}
          </button>

          {selectedRunIds.length >
            0 && (
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setSelectedRunIds(
                  []
                );

                setComparison(
                  null
                );

                setComparisonError(
                  ""
                );
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {comparisonError && (
        <p className="run-comparison-error">
          {comparisonError}
        </p>
      )}

      {viewState ===
        "loading" && (
        <p className="run-history-message">
          Loading run snapshot…
        </p>
      )}

      {viewState ===
        "failed" && (
        <p className="run-comparison-error">
          The run snapshot could not
          be loaded.
        </p>
      )}

      {viewedRun &&
        viewedSummary && (
        <div className="run-snapshot">
          <div className="run-snapshot-header">
            <div>
              <p className="eyebrow">
                Run snapshot
              </p>

              <h3>
                {
                  viewedRun.id
                }
              </h3>

              <span>
                {viewedRun.created_at
                  ? new Date(
                      viewedRun.created_at
                    ).toLocaleString()
                  : "Time unavailable"}
              </span>
            </div>

            <button
              className="text-button"
              type="button"
              onClick={() =>
                setViewedRun(
                  null
                )
              }
            >
              Close
            </button>
          </div>

          <div className="run-snapshot-stats">
            <div>
              <span>
                Verified signals
              </span>

              <strong>
                {
                  viewedSummary
                    .verifiedSignals
                }
              </strong>
            </div>

            <div>
              <span>
                High confidence
              </span>

              <strong>
                {
                  viewedSummary
                    .confidence
                    .high
                }
              </strong>
            </div>

            <div>
              <span>
                Medium confidence
              </span>

              <strong>
                {
                  viewedSummary
                    .confidence
                    .medium
                }
              </strong>
            </div>
          </div>

          <div className="run-snapshot-top">
            <span>
              Top finding
            </span>

            <strong>
              {viewedSummary
                .topInsight
                ?.title ??
                "No ranked insight"}
            </strong>
          </div>
        </div>
      )}

      {comparison && (
        <div className="run-comparison">
          <div className="run-comparison-header">
            <div>
              <p className="eyebrow">
                Run comparison
              </p>

              <h3>
                What changed?
              </h3>

              <p>
                Comparing persisted
                verified and ranked
                analytical results.
                No AI calculations are
                introduced here.
              </p>
            </div>

            <div className="run-comparison-dates">
              <span>
                Baseline
              </span>

              <strong>
                {comparison
                  .baseline
                  .created_at
                  ? new Date(
                      comparison
                        .baseline
                        .created_at
                    ).toLocaleString()
                  : comparison
                      .baseline.id}
              </strong>

              <span>
                → Newer run
              </span>

              <strong>
                {comparison
                  .current
                  .created_at
                  ? new Date(
                      comparison
                        .current
                        .created_at
                    ).toLocaleString()
                  : comparison
                      .current.id}
              </strong>
            </div>
          </div>

          <div className="run-comparison-stats">
            <div>
              <span>
                Verified signals
              </span>

              <strong>
                {
                  comparison
                    .baselineSummary
                    .verifiedSignals
                }
                {" → "}
                {
                  comparison
                    .currentSummary
                    .verifiedSignals
                }
              </strong>
            </div>

            <div>
              <span>
                High confidence
              </span>

              <strong>
                {
                  comparison
                    .baselineSummary
                    .confidence
                    .high
                }
                {" → "}
                {
                  comparison
                    .currentSummary
                    .confidence
                    .high
                }
              </strong>
            </div>

            <div>
              <span>
                New signals
              </span>

              <strong>
                {
                  comparison
                    .added
                    .length
                }
              </strong>
            </div>

            <div>
              <span>
                No longer detected
              </span>

              <strong>
                {
                  comparison
                    .removed
                    .length
                }
              </strong>
            </div>

            <div>
              <span>
                Changed signals
              </span>

              <strong>
                {
                  comparison
                    .changed
                    .length
                }
              </strong>
            </div>
          </div>

          <div className="run-top-change">
            <span>
              Top finding
            </span>

            <div>
              <strong>
                {comparison
                  .baselineSummary
                  .topInsight
                  ?.title ??
                  "None"}
              </strong>

              <span>
                →
              </span>

              <strong>
                {comparison
                  .currentSummary
                  .topInsight
                  ?.title ??
                  "None"}
              </strong>
            </div>
          </div>

          <div className="run-change-grid">
            <RunChangeList
              title="New signals"
              description="Present in the newer run only"
              items={
                comparison.added
              }
            />

            <RunChangeList
              title="No longer detected"
              description="Present in the baseline only"
              items={
                comparison.removed
              }
            />

            <RunChangeList
              title="Changed signals"
              description="Same analytical signal with changed ranking or confidence"
              items={
                comparison.changed
              }
              type="changed"
            />
          </div>
        </div>
      )}
    </section>
  );
}


function CorrelationScatterPlot({
  visualization,
}) {
  const points =
    visualization?.points ?? [];

  if (!points.length) {
    return null;
  }

  const width = 520;
  const height = 250;

  const padding = {
    top: 18,
    right: 18,
    bottom: 46,
    left: 54,
  };

  const xValues = points.map(
    (point) => Number(point.x)
  );

  const yValues = points.map(
    (point) => Number(point.y)
  );

  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  const plotWidth =
    width -
    padding.left -
    padding.right;

  const plotHeight =
    height -
    padding.top -
    padding.bottom;

  const scaleX = (value) =>
    padding.left +
    ((value - xMin) /
      (xMax - xMin || 1)) *
      plotWidth;

  const scaleY = (value) =>
    padding.top +
    plotHeight -
    ((value - yMin) /
      (yMax - yMin || 1)) *
      plotHeight;

  return (
    <div className="scatter-chart">
      <div className="scatter-heading">
        <div>
          <strong>
            Observed relationship
          </strong>

          <span>
            {visualization.x_column}
            {" vs "}
            {visualization.y_column}
          </span>
        </div>

        <small>
          {visualization.displayed_points}
          {" of "}
          {visualization.total_points}
          {" observations"}
        </small>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={
          `${visualization.x_column} versus ` +
          `${visualization.y_column} scatter plot`
        }
      >
        <line
          className="scatter-axis"
          x1={padding.left}
          y1={padding.top + plotHeight}
          x2={padding.left + plotWidth}
          y2={padding.top + plotHeight}
        />

        <line
          className="scatter-axis"
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={padding.top + plotHeight}
        />

        <text
          className="scatter-tick"
          x={padding.left}
          y={height - 24}
        >
          {formatValue(xMin)}
        </text>

        <text
          className="scatter-tick"
          x={padding.left + plotWidth}
          y={height - 24}
          textAnchor="end"
        >
          {formatValue(xMax)}
        </text>

        <text
          className="scatter-tick"
          x={padding.left - 8}
          y={padding.top + 4}
          textAnchor="end"
        >
          {formatValue(yMax)}
        </text>

        <text
          className="scatter-tick"
          x={padding.left - 8}
          y={padding.top + plotHeight}
          textAnchor="end"
        >
          {formatValue(yMin)}
        </text>

        {points.map(
          (point, index) => (
            <circle
              className="scatter-point"
              key={`${point.x}-${point.y}-${index}`}
              cx={scaleX(
                Number(point.x)
              )}
              cy={scaleY(
                Number(point.y)
              )}
              r="4"
            >
              <title>
                {visualization.x_column}
                {": "}
                {formatValue(point.x)}
                {" · "}
                {visualization.y_column}
                {": "}
                {formatValue(point.y)}
              </title>
            </circle>
          )
        )}

        <text
          className="scatter-axis-label"
          x={
            padding.left +
            plotWidth / 2
          }
          y={height - 5}
          textAnchor="middle"
        >
          {visualization.x_column}
        </text>

        <text
          className="scatter-axis-label"
          transform={
            `translate(14 ${
              padding.top +
              plotHeight / 2
            }) rotate(-90)`
          }
          textAnchor="middle"
        >
          {visualization.y_column}
        </text>
      </svg>

      {visualization.sampled && (
        <p className="scatter-note">
          Display limited to a deterministic
          sample of{" "}
          {visualization.displayed_points}{" "}
          points from{" "}
          {visualization.total_points}{" "}
          observations.
        </p>
      )}
    </div>
  );
}

function GroupComparisonBarChart({
  visualization,
}) {
  const groups =
    visualization?.groups ?? [];

  if (!groups.length) {
    return null;
  }

  const means = groups
    .map((group) =>
      Number(group.mean)
    )
    .filter(Number.isFinite);

  if (!means.length) {
    return null;
  }

  const minimum = Math.min(
    0,
    ...means
  );

  const maximum = Math.max(
    0,
    ...means
  );

  const range =
    maximum - minimum || 1;

  const zeroPosition =
    ((0 - minimum) / range) * 100;

  return (
    <div className="group-chart">
      <div className="group-chart-heading">
        <div>
          <strong>
            Average{" "}
            {visualization.measure}
            {" by "}
            {visualization.dimension}
          </strong>

          <span>
            Deterministic group means
          </span>
        </div>

        <small>
          {visualization.displayed_groups}
          {" of "}
          {visualization.total_groups}
          {" groups"}
        </small>
      </div>

      <div className="group-bars">
        {groups.map(
          (group, index) => {
            const mean = Number(
              group.mean
            );

            if (
              !Number.isFinite(mean)
            ) {
              return null;
            }

            const valuePosition =
              ((mean - minimum) /
                range) *
              100;

            const barLeft =
              Math.min(
                zeroPosition,
                valuePosition
              );

            const barWidth =
              Math.max(
                Math.abs(
                  valuePosition -
                    zeroPosition
                ),
                1
              );

            return (
              <div
                className="group-bar-row"
                key={
                  `${group.label}-` +
                  `${index}`
                }
              >
                <div className="group-bar-label">
                  <strong>
                    {group.label}
                  </strong>

                  <small>
                    n={group.count}
                  </small>
                </div>

                <div className="group-bar-track">
                  <span
                    className="group-zero-line"
                    style={{
                      left:
                        `${zeroPosition}%`,
                    }}
                  />

                  <span
                    className="group-bar-fill"
                    style={{
                      left:
                        `${barLeft}%`,
                      width:
                        `${barWidth}%`,
                    }}
                  />
                </div>

                <div className="group-bar-value">
                  {formatValue(
                    group.mean
                  )}
                </div>
              </div>
            );
          }
        )}
      </div>

      {visualization.sampled && (
        <p className="group-chart-note">
          Showing the highest and
          lowest{" "}
          {visualization.displayed_groups}
          {" groups from "}
          {visualization.total_groups}
          {" total groups."}
        </p>
      )}
    </div>
  );
}

function TimeSeriesLineChart({
  result,
}) {
  const measure = result?.measure;
  const dateColumn = result?.date;

  const sourceData =
    result?.data ?? [];

  const sampledData =
    sampleSeriesPoints(
      sourceData
    );

  const points = sampledData
    .map((row) => ({
      date: row?.[dateColumn],
      value: Number(
        row?.[measure]
      ),
    }))
    .filter(
      (point) =>
        point.date !==
          null &&
        point.date !==
          undefined &&
        Number.isFinite(
          point.value
        )
    );

  if (
    !measure ||
    !dateColumn ||
    points.length < 2
  ) {
    return null;
  }

  const width = 720;
  const height = 280;

  const padding = {
    top: 22,
    right: 22,
    bottom: 52,
    left: 64,
  };

  const chartWidth =
    width -
    padding.left -
    padding.right;

  const chartHeight =
    height -
    padding.top -
    padding.bottom;

  const values = points.map(
    (point) => point.value
  );

  const minimum =
    Math.min(...values);

  const maximum =
    Math.max(...values);

  const valueRange =
    maximum - minimum || 1;

  const coordinates =
    points.map(
      (point, index) => {
        const x =
          padding.left +
          (
            index /
            (points.length - 1)
          ) *
            chartWidth;

        const y =
          padding.top +
          chartHeight -
          (
            (
              point.value -
              minimum
            ) /
            valueRange
          ) *
            chartHeight;

        return {
          ...point,
          x,
          y,
        };
      }
    );

  const polylinePoints =
    coordinates
      .map(
        (point) =>
          `${point.x},${point.y}`
      )
      .join(" ");

  const first =
    coordinates[0];

  const last =
    coordinates[
      coordinates.length - 1
    ];

  return (
    <article className="time-series-card">
      <div className="time-series-heading">
        <div>
          <p className="eyebrow">
            Deterministic trend analysis
          </p>

          <h3>
            {measure}
            {" over "}
            {dateColumn}
          </h3>

          <p>
            Sorted observations from
            the deterministic analytics
            engine. AI is not used to
            calculate this chart.
          </p>
        </div>

        <StatusPill
          tone="success"
        >
          Deterministic
        </StatusPill>
      </div>

      <div className="time-series-meta">
        <span>
          <strong>
            {result.sample_size ??
              sourceData.length}
          </strong>
          {" observations"}
        </span>

        <span>
          <strong>
            {formatValue(
              minimum
            )}
          </strong>
          {" minimum"}
        </span>

        <span>
          <strong>
            {formatValue(
              maximum
            )}
          </strong>
          {" maximum"}
        </span>
      </div>

      <div className="time-series-chart">
        <svg
          viewBox={
            `0 0 ${width} ${height}`
          }
          role="img"
          aria-label={
            `${measure} over ` +
            `${dateColumn} line chart`
          }
        >
          <line
            className="time-series-axis"
            x1={padding.left}
            y1={
              padding.top +
              chartHeight
            }
            x2={
              padding.left +
              chartWidth
            }
            y2={
              padding.top +
              chartHeight
            }
          />

          <line
            className="time-series-axis"
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={
              padding.top +
              chartHeight
            }
          />

          <text
            className="time-series-tick"
            x={
              padding.left - 10
            }
            y={
              padding.top + 4
            }
            textAnchor="end"
          >
            {formatValue(
              maximum
            )}
          </text>

          <text
            className="time-series-tick"
            x={
              padding.left - 10
            }
            y={
              padding.top +
              chartHeight
            }
            textAnchor="end"
          >
            {formatValue(
              minimum
            )}
          </text>

          <polyline
            className="time-series-line"
            points={
              polylinePoints
            }
          />

          {coordinates.map(
            (
              point,
              index
            ) => (
              <circle
                className="time-series-point"
                key={
                  `${point.date}-` +
                  `${index}`
                }
                cx={point.x}
                cy={point.y}
                r={
                  coordinates.length >
                  80
                    ? 1.8
                    : 3
                }
              >
                <title>
                  {formatChartDate(
                    point.date
                  )}
                  {": "}
                  {formatValue(
                    point.value
                  )}
                </title>
              </circle>
            )
          )}

          <text
            className="time-series-tick"
            x={first.x}
            y={
              height - 24
            }
          >
            {formatChartDate(
              first.date
            )}
          </text>

          <text
            className="time-series-tick"
            x={last.x}
            y={
              height - 24
            }
            textAnchor="end"
          >
            {formatChartDate(
              last.date
            )}
          </text>

          <text
            className="time-series-axis-label"
            x={
              padding.left +
              chartWidth / 2
            }
            y={height - 4}
            textAnchor="middle"
          >
            {dateColumn}
          </text>

          <text
            className="time-series-axis-label"
            transform={
              `translate(15 ${
                padding.top +
                chartHeight / 2
              }) rotate(-90)`
            }
            textAnchor="middle"
          >
            {measure}
          </text>
        </svg>
      </div>

      {sourceData.length >
        sampledData.length && (
        <p className="time-series-note">
          Visualization displays a
          deterministic sample of{" "}
          {sampledData.length}
          {" from "}
          {sourceData.length}
          {" observations. "}
          The underlying analysis uses
          the complete time series.
        </p>
      )}
    </article>
  );
}


function TimeSeriesResults({
  analysis,
}) {
  const results =
    analysis?.analysis_results
      ?.filter(
        (result) =>
          result.type ===
            "time_series" &&
          Array.isArray(
            result.data
          ) &&
          result.data.length > 1
      ) ?? [];

  if (!results.length) {
    return null;
  }

  return (
    <section className="time-series-results">
      <div className="time-series-section-heading">
        <div>
          <p className="eyebrow">
            Time-series analysis
          </p>

          <h2>
            Deterministic trends
          </h2>

          <p>
            These charts show the
            sorted analytical series
            directly. They are not
            AI-generated insights.
          </p>
        </div>
      </div>

      <div className="time-series-grid">
        {results.map(
          (
            result,
            index
          ) => (
            <TimeSeriesLineChart
              key={
                `${result.measure}-` +
                `${result.date}-` +
                `${index}`
              }
              result={result}
            />
          )
        )}
      </div>
    </section>
  );
}

function EvidenceVisual({
  insight,
}) {
  const evidence =
    insight.evidence ?? {};

  if (
    insight.insight_type === "correlation" &&
    typeof evidence.correlation === "number"
  ) {
    const width = Math.min(
      100,
      Math.abs(
        evidence.correlation
      ) * 100
    );
    const visualization =
      insight.calculation
        ?.visualization;

    return (
      <div className="evidence-visual">
        <div className="visual-label">
          <span>
            Correlation strength
          </span>

          <strong>
            {formatValue(
              evidence.correlation
            )}
          </strong>
        </div>

        <div className="bar-track">
          <div
            className="bar-fill"
            style={{
              width: `${width}%`,
            }}
          />
        </div>

        <CorrelationScatterPlot
          visualization={
            visualization
          }
        />
      </div>
    );
  }

  if (
  insight.insight_type ===
  "group_difference"
) {
  const visualization =
    insight.calculation
      ?.visualization;

  return (
    <GroupComparisonBarChart
      visualization={
        visualization
      }
    />
  );
}

  if (
    insight.insight_type === "outlier" &&
    evidence.outliers?.length
  ) {
    return (
      <div className="outlier-list">
        {evidence.outliers.map(
          (value, index) => (
            <span
              key={`${value}-${index}`}
            >
              {formatValue(value)}
            </span>
          )
        )}
      </div>
    );
  }

  return null;
}



function renderInlineMarkdown(
  text,
  keyPrefix = "inline"
) {
  const parts = String(
    text ?? ""
  ).split(
    /(\*\*[^*]+\*\*)/g
  );

  return parts.map(
    (part, index) => {
      if (
        part.startsWith("**") &&
        part.endsWith("**") &&
        part.length > 4
      ) {
        return (
          <strong
            key={
              `${keyPrefix}-bold-${index}`
            }
          >
            {part.slice(2, -2)}
          </strong>
        );
      }

      return part;
    }
  );
}


function MarkdownText({
  text,
}) {
  if (!text) {
    return null;
  }

  const lines = String(text)
    .replace(/\r\n/g, "\n")
    .split("\n");

  const elements = [];

  let paragraphLines = [];
  let listItems = [];

  const flushParagraph = () => {
    if (!paragraphLines.length) {
      return;
    }

    const content =
      paragraphLines.join(" ");

    const key =
      `paragraph-${elements.length}`;

    elements.push(
      <p key={key}>
        {renderInlineMarkdown(
          content,
          key
        )}
      </p>
    );

    paragraphLines = [];
  };

  const flushList = () => {
    if (!listItems.length) {
      return;
    }

    const key =
      `list-${elements.length}`;

    elements.push(
      <ul
        className="markdown-list"
        key={key}
      >
        {listItems.map(
          (item, index) => (
            <li
              key={
                `${key}-${index}`
              }
            >
              {renderInlineMarkdown(
                item,
                `${key}-${index}`
              )}
            </li>
          )
        )}
      </ul>
    );

    listItems = [];
  };

  lines.forEach(
    (rawLine) => {
      const line =
        rawLine.trim();

      if (!line) {
        flushParagraph();
        flushList();
        return;
      }

      if (/^-{3,}$/.test(line)) {
        flushParagraph();
        flushList();

        elements.push(
          <hr
            className="markdown-divider"
            key={
              `divider-${elements.length}`
            }
          />
        );

        return;
      }

      const headingMatch =
        line.match(
          /^#{1,4}\s+(.+)$/
        );

      if (headingMatch) {
        flushParagraph();
        flushList();

        const key =
          `heading-${elements.length}`;

        elements.push(
          <h5
            className="markdown-heading"
            key={key}
          >
            {renderInlineMarkdown(
              headingMatch[1],
              key
            )}
          </h5>
        );

        return;
      }

      const bulletMatch =
        line.match(
          /^[-*]\s+(.+)$/
        );

      if (bulletMatch) {
        flushParagraph();

        listItems.push(
          bulletMatch[1]
        );

        return;
      }

      flushList();

      paragraphLines.push(
        line
      );
    }
  );

  flushParagraph();
  flushList();

  return (
    <div className="markdown-body">
      {elements}
    </div>
  );
}


function InsightCard({
  insight,
  explanation,
  recommendation,
}) {
  const evidence = Object.entries(
    insight.evidence ?? {}
  ).filter(
    ([, value]) =>
      value !== null &&
      value !== undefined
  );

  const confidence =
    insight.confidence ?? {};

  return (
    <article className="insight-card">
      <div className="insight-topline">
        <StatusPill tone="dark">
          {insight.insight_type.replaceAll(
            "_",
            " "
          )}
        </StatusPill>

        <StatusPill tone="success">
          Verified
        </StatusPill>
      </div>

      <h3>
        {insight.title}
      </h3>

      <p className="source-columns">
        {insight.source_columns?.join(
          " · "
        )}
      </p>

      <EvidenceVisual
        insight={insight}
      />

      <dl className="evidence-grid">
        {evidence.map(
          ([key, value]) => (
            <div key={key}>
              <dt>
                {key.replaceAll(
                  "_",
                  " "
                )}
              </dt>

              <dd>
                {formatValue(
                  value
                )}
              </dd>
            </div>
          )
        )}
      </dl>

      <div className="confidence-row">
        <span>
          Confidence
        </span>

        <strong>
          {confidence.level ??
            "Not available"}

          {typeof confidence.score ===
          "number"
            ? ` · ${formatValue(
                confidence.score
              )}`
            : ""}
        </strong>
      </div>

      <div className="explanation-block">
        <div className="explanation-heading">
          <h4>
            Grounded explanation
          </h4>

          {explanation?.status === "approved" &&
            explanation?.source && (
              <span
                className={`explanation-source ${
                  explanation.source === "llm"
                    ? "ai"
                    : "deterministic"
                }`}
              >
                {explanation.source === "llm"
                  ? "AI-assisted"
                  : "Deterministic"}
              </span>
            )}
        </div>

        {explanation?.status ===
        "approved" ? (
          <MarkdownText
            text={
              explanation.explanation
                .text
            }
          />
        ) : (
          <p className="muted">
            {explanation?.status ===
            "unavailable"
              ? "Explanation is currently unavailable. The verified analytical evidence remains available above."
              : "No approved explanation is available for this insight."}
          </p>
        )}
      </div>

      {recommendation?.recommendation && (
        <div className="recommendation-block">
          <h4>
            Recommended next step
          </h4>

          <p>
            {
              recommendation
                .recommendation
                .action
            }
          </p>

          <small>
            {
              recommendation
                .recommendation
                .reason
            }
          </small>
        </div>
      )}
    </article>
  );
}



function getExecutiveMetric(
  insight
) {
  const evidence =
    insight?.evidence ?? {};

  if (
    insight?.insight_type ===
      "time_series_trend" &&
    typeof evidence.percentage_change ===
      "number"
  ) {
    const value =
      evidence.percentage_change;

    return {
      label: "Overall change",
      value:
        `${value > 0 ? "+" : ""}` +
        `${formatValue(value)}%`,
    };
  }

  if (
    insight?.insight_type ===
      "correlation" &&
    typeof evidence.correlation ===
      "number"
  ) {
    return {
      label: "Correlation",
      value: formatValue(
        evidence.correlation
      ),
    };
  }

  if (
    insight?.insight_type ===
      "group_difference" &&
    typeof evidence.percentage_difference ===
      "number"
  ) {
    return {
      label: "Difference",
      value:
        `${formatValue(
          Math.abs(
            evidence.percentage_difference
          )
        )}%`,
    };
  }

  if (
    insight?.insight_type ===
      "outlier" &&
    typeof evidence.outlier_count ===
      "number"
  ) {
    return {
      label: "Outliers",
      value: formatValue(
        evidence.outlier_count
      ),
    };
  }

  if (
    typeof insight?.score ===
    "number"
  ) {
    return {
      label: "Priority score",
      value: formatValue(
        insight.score
      ),
    };
  }

  return null;
}


function ExecutiveSummary({
  insights,
}) {
  if (!insights?.length) {
    return null;
  }

  const confidenceCounts =
    insights.reduce(
      (counts, insight) => {
        const level =
          insight.confidence
            ?.level?.toLowerCase();

        if (
          level === "high" ||
          level === "medium" ||
          level === "low"
        ) {
          counts[level] += 1;
        }

        return counts;
      },
      {
        high: 0,
        medium: 0,
        low: 0,
      }
    );

  const topInsight =
    insights[0];

  const priorityInsights =
    insights.slice(1, 4);

  const topMetric =
    getExecutiveMetric(
      topInsight
    );

  return (
    <section className="executive-summary">
      <div className="executive-summary-header">
        <div>
          <p className="eyebrow">
            Executive summary
          </p>

          <h2>
            What matters most
          </h2>

          <p>
            A concise view of the
            highest-ranked verified
            signals from the
            deterministic analysis.
          </p>
        </div>

        <StatusPill tone="success">
          Verified only
        </StatusPill>
      </div>

      <div className="executive-summary-stats">
        <div className="executive-stat">
          <span>
            Verified signals
          </span>

          <strong>
            {insights.length}
          </strong>
        </div>

        <div className="executive-stat">
          <span>
            High confidence
          </span>

          <strong>
            {
              confidenceCounts.high
            }
          </strong>
        </div>

        <div className="executive-stat">
          <span>
            Medium confidence
          </span>

          <strong>
            {
              confidenceCounts.medium
            }
          </strong>
        </div>

        <div className="executive-stat">
          <span>
            Low confidence
          </span>

          <strong>
            {
              confidenceCounts.low
            }
          </strong>
        </div>
      </div>

      <div className="executive-summary-grid">
        <article className="executive-top-finding">
          <div className="executive-finding-topline">
            <div>
              <span className="executive-rank">
                #1
              </span>

              <span>
                Top verified finding
              </span>
            </div>

            <StatusPill
              tone={
                topInsight
                  .confidence
                  ?.level ===
                "high"
                  ? "success"
                  : "dark"
              }
            >
              {
                topInsight
                  .confidence
                  ?.level ??
                "Confidence unavailable"
              }
            </StatusPill>
          </div>

          <h3>
            {topInsight.title}
          </h3>

          <p className="executive-source">
            {
              topInsight
                .source_columns
                ?.join(" · ")
            }
          </p>

          <div className="executive-top-metrics">
            {topMetric && (
              <div>
                <span>
                  {topMetric.label}
                </span>

                <strong>
                  {topMetric.value}
                </strong>
              </div>
            )}

            {typeof
              topInsight.score ===
              "number" && (
              <div>
                <span>
                  Priority score
                </span>

                <strong>
                  {formatValue(
                    topInsight.score
                  )}
                </strong>
              </div>
            )}
          </div>
        </article>

        {priorityInsights.length >
          0 && (
          <aside className="executive-priority-list">
            <div className="executive-priority-heading">
              <strong>
                Other priority signals
              </strong>

              <span>
                Next highest-ranked
                findings
              </span>
            </div>

            <ol>
              {priorityInsights.map(
                (
                  insight,
                  index
                ) => {
                  const metric =
                    getExecutiveMetric(
                      insight
                    );

                  return (
                    <li
                      key={
                        `${insight.insight_type}-` +
                        `${insight.title}`
                      }
                    >
                      <div className="executive-priority-rank">
                        {index + 2}
                      </div>

                      <div className="executive-priority-copy">
                        <strong>
                          {insight.title}
                        </strong>

                        <span>
                          {
                            insight
                              .confidence
                              ?.level ??
                            "Confidence unavailable"
                          }
                          {metric
                            ? ` · ${metric.label}: ${metric.value}`
                            : ""}
                        </span>
                      </div>
                    </li>
                  );
                }
              )}
            </ol>
          </aside>
        )}
      </div>

      <p className="executive-summary-note">
        This summary reorganizes
        already-verified analytical
        results. It does not introduce
        new AI-generated calculations.
      </p>
    </section>
  );
}


function ResultsDashboard({
  analysis,
}) {
  const insights =
    analysis.ranked_insights ?? [];

  const [
    exportState,
    setExportState,
  ] = useState("idle");

  const [
    exportMessage,
    setExportMessage,
  ] = useState("");

  async function handleExport(
    format
  ) {
    if (
      !analysis.analysis_run_id
    ) {
      return;
    }

    setExportState(format);
    setExportMessage("");

    try {
      const filename =
        await downloadAnalysisRunExport(
          analysis.analysis_run_id,
          format
        );

      setExportMessage(
        `${filename} exported`
      );
    } catch (error) {
      setExportMessage(
        error.message
      );
    } finally {
      setExportState("idle");
    }
  }

  const explanationByTitle =
    useMemo(
      () =>
        new Map(
          (
            analysis.explained_insights ??
            []
          ).map((item) => [
            item.title,
            item.explanation,
          ])
        ),
      [analysis]
    );

  const recommendationByTitle =
    useMemo(
      () =>
        new Map(
          (
            analysis.recommended_insights ??
            []
          ).map((item) => [
            item.title,
            item.recommendation,
          ])
        ),
      [analysis]
    );

  return (
    <section className="results">
      <div className="results-header">
        <div>
          <p className="eyebrow">
            Analysis results
          </p>

          <h2>
            Verified business signals
          </h2>

          <p>
            Only insights that passed deterministic verification are shown.
          </p>

          {analysis.analysis_run_id && (
            <p className="run-id">
              Analysis run ·{" "}
              {analysis.analysis_run_id}
            </p>
          )}
        </div>

        <div className="results-header-actions">
          <StatusPill
            tone={
              analysis.status ===
              "completed"
                ? "success"
                : "warning"
            }
          >
            {analysis.status?.replaceAll(
              "_",
              " "
            )}
          </StatusPill>

          {analysis.analysis_run_id && (
            <div className="export-controls">
              <span>
                Export verified report
              </span>

              <div>
                <button
                  type="button"
                  className="export-button"
                  disabled={
                    exportState !==
                    "idle"
                  }
                  onClick={() =>
                    handleExport(
                      "csv"
                    )
                  }
                >
                  {exportState ===
                  "csv"
                    ? "Exporting…"
                    : "CSV"}
                </button>

                <button
                  type="button"
                  className="export-button primary"
                  disabled={
                    exportState !==
                    "idle"
                  }
                  onClick={() =>
                    handleExport(
                      "xlsx"
                    )
                  }
                >
                  {exportState ===
                  "xlsx"
                    ? "Exporting…"
                    : "Excel"}
                </button>

                <button
                  type="button"
                  className="export-button primary"
                  disabled={
                    exportState !==
                    "idle"
                  }
                  onClick={() =>
                    handleExport(
                      "pdf"
                    )
                  }
                >
                  {exportState ===
                  "pdf"
                    ? "Exporting…"
                    : "PDF"}
                </button>
              </div>

              {exportMessage && (
                <small>
                  {exportMessage}
                </small>
              )}
            </div>
          )}
        </div>
      </div>

      <ExecutiveSummary
        insights={insights}
      />

      <TimeSeriesResults
        analysis={analysis}
      />

      {insights.length ? (
        <div className="insight-grid">
          {insights.map(
            (insight) => (
              <InsightCard
                key={`${insight.insight_type}-${insight.title}`}
                insight={insight}
                explanation={explanationByTitle.get(
                  insight.title
                )}
                recommendation={recommendationByTitle.get(
                  insight.title
                )}
              />
            )
          )}
        </div>
      ) : (
        <div className="empty-state">
          <h3>
            No verified insights were found
          </h3>

          <p>
            The dataset completed analysis, but no discovered insight met the verification threshold.
          </p>
        </div>
      )}
    </section>
  );
}


export default function App({
  currentUser,
  onLogout,
}) {
  const fileInput =
    useRef(null);

  const [
    upload,
    setUpload,
  ] = useState(null);

  const [
    overview,
    setOverview,
  ] = useState(null);

  const [
    plan,
    setPlan,
  ] = useState(null);

  const [
    analysis,
    setAnalysis,
  ] = useState(null);

  const [
    history,
    setHistory,
  ] = useState(null);

  const [
    state,
    setState,
  ] = useState("idle");

  const [
    error,
    setError,
  ] = useState("");

  const [
    datasetLibrary,
    setDatasetLibrary,
  ] = useState({
    count: 0,
    datasets: [],
  });

  const [
    libraryLoading,
    setLibraryLoading,
  ] = useState(true);

  const [
    libraryError,
    setLibraryError,
  ] = useState("");


  async function refreshDatasetLibrary() {
    setLibraryLoading(true);
    setLibraryError("");

    try {
      const result =
        await listOwnedDatasets();

      setDatasetLibrary(
        result
      );
    } catch (nextError) {
      setLibraryError(
        nextError.message
      );
    } finally {
      setLibraryLoading(false);
    }
  }


  useEffect(() => {
    refreshDatasetLibrary();
  }, [currentUser?.id]);


  async function handleOpenDataset(
    dataset
  ) {
    const latest =
      dataset.latest_version;

    if (!latest) {
      return;
    }

    setError("");
    setAnalysis(null);
    setOverview(null);
    setPlan(null);
    setHistory(null);

    setUpload({
      dataset_id: dataset.id,
      dataset_version_id:
        latest.id,
      version_number:
        latest.version_number,
      file_name:
        latest.file_name,
    });

    setState("inspecting");

    try {
      const [
        nextOverview,
        nextPlan,
        nextHistory,
      ] = await Promise.all([
        loadDatasetOverview(
          latest.id
        ),

        loadDatasetPlan(
          latest.id
        ),

        loadAnalysisRuns(
          latest.id
        ),
      ]);

      setOverview(
        nextOverview
      );

      setPlan(
        nextPlan
      );

      setHistory(
        nextHistory
      );

      setState("ready");
    } catch (nextError) {
      setState("idle");

      setError(
        nextError.message
      );
    }
  }


  async function handleFile(file) {
    if (!file) {
      return;
    }

    const extension = file.name
      .split(".")
      .pop()
      ?.toLowerCase();

    if (
      !supportedExtensions.includes(
        extension
      )
    ) {
      setError(
        "Choose a CSV, XLSX, or XLS file."
      );

      return;
    }

    setError("");
    setAnalysis(null);
    setOverview(null);
    setUpload(null);
    setPlan(null);
    setHistory(null);

    setState("uploading");

    try {
      const uploaded =
        await uploadDataset(file);

      setUpload(uploaded);

      setState("inspecting");

      const [
        nextOverview,
        nextPlan,
      ] = await Promise.all([
        loadDatasetOverview(
          uploaded.dataset_version_id
        ),

        loadDatasetPlan(
          uploaded.dataset_version_id
        ),
      ]);

      setOverview(
        nextOverview
      );

      setPlan(
        nextPlan
      );

      setState("ready");

      await refreshDatasetLibrary();
    } catch (nextError) {
      setState("idle");

      setError(
        nextError.message
      );
    }
  }


  async function handleAnalyze() {
    if (
      !upload ||
      !overview?.validation.valid
    ) {
      return;
    }

    setError("");
    setState("analyzing");

    try {
      const result =
        await analyzeDataset(
          upload.dataset_version_id
        );

      setAnalysis({
        ...result.analysis,
        analysis_run_id:
          result.analysis_run_id,
      });

      const nextHistory =
        await loadAnalysisRuns(
          upload.dataset_version_id
        );

      setHistory(
        nextHistory
      );

      setState("complete");
    } catch (nextError) {
      setState("ready");

      setError(
        nextError.message
      );
    }
  }


  return (
    <main>
      <nav>
        <a
          className="brand"
          href="#top"
        >
          Signal
          <span>Ledger</span>
        </a>

        <div className="account-nav">
          <span className="nav-note">
            {currentUser?.email}
          </span>

          <button
            type="button"
            className="logout-button"
            onClick={onLogout}
          >
            Sign out
          </button>
        </div>
      </nav>

      <DatasetLibrary
        library={datasetLibrary}
        loading={libraryLoading}
        error={libraryError}
        onOpenDataset={
          handleOpenDataset
        }
        onRefresh={
          refreshDatasetLibrary
        }
      />

      <section
        className="hero"
        id="top"
      >
        <div>
          <p className="eyebrow">
            Business intelligence, grounded in evidence
          </p>

          <h1>
            Find the signal.
            <br />

            <em>
              Keep the proof.
            </em>
          </h1>

          <p className="hero-copy">
            Upload a business dataset to discover verified insights, practical next steps, and AI explanations grounded in deterministic analysis.
          </p>

          <div className="upload-card">
            <input
              ref={fileInput}
              id="dataset-file"
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) =>
                handleFile(
                  event.target
                    .files?.[0]
                )
              }
            />

            <label
              htmlFor="dataset-file"
              className="upload-button"
            >
              Choose a dataset
            </label>

            <p>
              CSV, XLSX, or XLS · maximum 25 MB
            </p>

            {state ===
              "uploading" && (
              <p className="loading">
                Uploading dataset…
              </p>
            )}

            {state ===
              "inspecting" && (
              <p className="loading">
                Running validation, PII scan, profiling, semantic detection, and analytics planning…
              </p>
            )}
          </div>
        </div>

        <TrustPanel />
      </section>

      {error && (
        <div
          className="page-notice error"
          role="alert"
        >
          <strong>
            Unable to continue
          </strong>

          <span>
            {error}
          </span>
        </div>
      )}

      {upload &&
        overview && (
          <>
            <DatasetOverview
              upload={upload}
              overview={overview}
            />

            <PlanSummary
              plan={plan}
            />

            <section className="analysis-cta card">
              <div>
                <p className="eyebrow">
                  Ready when you are
                </p>

                <h2>
                  Run verified analysis
                </h2>

                <p>
                  The deterministic plan above will now be executed. Discovered insights must pass verification before they can be ranked or explained by AI.
                </p>
              </div>

              <button
                type="button"
                onClick={
                  handleAnalyze
                }
                disabled={
                  state ===
                    "analyzing" ||
                  !overview
                    .validation
                    .valid
                }
              >
                {state ===
                "analyzing"
                  ? "Analysis running on the server…"
                  : "Run analysis"}
              </button>
            </section>

            {state ===
              "analyzing" && (
              <div className="page-notice loading">
                <strong>
                  Analysis in progress
                </strong>

                <span>
                  Waiting for the backend to return completed results. No progress is estimated or fabricated.
                </span>
              </div>
            )}
          </>
        )}

      {analysis && (
        <ResultsDashboard
          analysis={analysis}
        />
      )}

      {history && (
        <AnalysisRunHistory
          history={history}
          currentRunId={
            analysis?.analysis_run_id
          }
        />
      )}

      {!upload &&
        !error && (
          <section className="empty-state initial">
            <h2>
              Start with a dataset
            </h2>

            <p>
              Your data is validated and scanned for protected columns before analysis begins.
            </p>
          </section>
        )}
    </main>
  );
}
