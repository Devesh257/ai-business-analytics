import {
  useState,
} from "react";


function formatVersionDate(value) {
  if (!value) {
    return "Date unavailable";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return String(value);
  }

  return date.toLocaleString(
    undefined,
    {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


export default function DatasetLibrary({
  library,
  loading,
  error,
  onOpenDataset,
  onOpenVersion,
  onLoadVersions,
  onRefresh,
  activeDatasetId,
  activeVersionId,
}) {
  const datasets =
    library?.datasets ?? [];

  const [
    expandedDatasetId,
    setExpandedDatasetId,
  ] = useState(null);

  const [
    versionsByDataset,
    setVersionsByDataset,
  ] = useState({});

  const [
    versionLoadingId,
    setVersionLoadingId,
  ] = useState(null);

  const [
    versionErrors,
    setVersionErrors,
  ] = useState({});


  async function toggleVersions(
    dataset
  ) {
    if (
      expandedDatasetId ===
      dataset.id
    ) {
      setExpandedDatasetId(null);
      return;
    }

    setExpandedDatasetId(
      dataset.id
    );

    setVersionErrors(
      (current) => ({
        ...current,
        [dataset.id]: "",
      })
    );

    setVersionLoadingId(
      dataset.id
    );

    try {
      const result =
        await onLoadVersions(
          dataset.id
        );

      setVersionsByDataset(
        (current) => ({
          ...current,
          [dataset.id]:
            result.versions ?? [],
        })
      );
    } catch (nextError) {
      setVersionErrors(
        (current) => ({
          ...current,
          [dataset.id]:
            nextError.message,
        })
      );
    } finally {
      setVersionLoadingId(null);
    }
  }


  return (
    <section className="card dataset-library">
      <div className="section-heading">
        <div>
          <p className="eyebrow">
            Your workspace
          </p>

          <h2>
            My datasets
          </h2>

          <p>
            Reopen datasets and browse
            historical versions without
            uploading them again.
          </p>
        </div>

        <button
          type="button"
          className="library-refresh"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading
            ? "Refreshing…"
            : "Refresh"}
        </button>
      </div>

      {error && (
        <div
          className="notice warning"
          role="alert"
        >
          {error}
        </div>
      )}

      {!loading &&
        !error &&
        datasets.length === 0 && (
          <div className="library-empty">
            <strong>
              No datasets yet
            </strong>

            <span>
              Upload your first business
              dataset below.
            </span>
          </div>
        )}

      {datasets.length > 0 && (
        <div className="dataset-library-grid">
          {datasets.map((dataset) => {
            const latest =
              dataset.latest_version;

            const expanded =
              expandedDatasetId ===
              dataset.id;

            const versions =
              versionsByDataset[
                dataset.id
              ] ?? [];

            const versionsLoading =
              versionLoadingId ===
              dataset.id;

            const versionError =
              versionErrors[
                dataset.id
              ];

            const datasetActive =
              activeDatasetId ===
              dataset.id;

            return (
              <article
                key={dataset.id}
                className={
                  datasetActive
                    ? (
                      "dataset-library-item "
                      + "dataset-library-item-active"
                    )
                    : "dataset-library-item"
                }
              >
                <div className="dataset-library-summary">
                  <div>
                    <div className="dataset-title-row">
                      <h3>
                        {dataset.name}
                      </h3>

                      {datasetActive && (
                        <span className="version-badge active">
                          Active
                        </span>
                      )}
                    </div>

                    <p>
                      {dataset.version_count}
                      {" "}
                      {dataset.version_count === 1
                        ? "version"
                        : "versions"}
                    </p>

                    {latest && (
                      <small>
                        Latest:{" "}
                        {latest.file_name}
                        {" · v"}
                        {
                          latest.version_number
                        }
                      </small>
                    )}
                  </div>

                  <div className="dataset-library-actions">
                    <button
                      type="button"
                      disabled={!latest}
                      onClick={() =>
                        onOpenDataset(
                          dataset
                        )
                      }
                    >
                      Open latest
                    </button>

                    <button
                      type="button"
                      className="secondary-button"
                      disabled={
                        !dataset.version_count
                      }
                      aria-expanded={
                        expanded
                      }
                      aria-controls={
                        `versions-${dataset.id}`
                      }
                      onClick={() =>
                        toggleVersions(
                          dataset
                        )
                      }
                    >
                      {expanded
                        ? "Hide versions"
                        : "Versions"}
                    </button>
                  </div>
                </div>

                {expanded && (
                  <div
                    id={
                      `versions-${dataset.id}`
                    }
                    className="dataset-version-panel"
                  >
                    {versionsLoading && (
                      <p className="loading">
                        Loading versions…
                      </p>
                    )}

                    {versionError && (
                      <div
                        className="notice warning"
                        role="alert"
                      >
                        {versionError}
                      </div>
                    )}

                    {!versionsLoading &&
                      !versionError &&
                      versions.length === 0 && (
                        <p className="version-empty">
                          No versions available.
                        </p>
                      )}

                    {!versionsLoading &&
                      versions.map(
                        (version) => {
                          const isLatest =
                            latest?.id ===
                            version.id;

                          const isActive =
                            activeVersionId ===
                            version.id;

                          return (
                            <div
                              key={version.id}
                              className={
                                isActive
                                  ? (
                                    "dataset-version-row "
                                    + "dataset-version-row-active"
                                  )
                                  : "dataset-version-row"
                              }
                            >
                              <div className="version-details">
                                <div className="version-heading">
                                  <strong>
                                    Version{" "}
                                    {
                                      version.version_number
                                    }
                                  </strong>

                                  {isLatest && (
                                    <span className="version-badge latest">
                                      Latest
                                    </span>
                                  )}

                                  {isActive && (
                                    <span className="version-badge active">
                                      Open
                                    </span>
                                  )}
                                </div>

                                <span>
                                  {
                                    version.file_name
                                  }
                                </span>

                                <small>
                                  {
                                    formatVersionDate(
                                      version.created_at
                                    )
                                  }
                                </small>
                              </div>

                              <button
                                type="button"
                                disabled={isActive}
                                onClick={() =>
                                  onOpenVersion(
                                    dataset,
                                    version
                                  )
                                }
                              >
                                {isActive
                                  ? "Current"
                                  : "Open version"}
                              </button>
                            </div>
                          );
                        }
                      )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
