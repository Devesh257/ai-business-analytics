export default function DatasetLibrary({
  library,
  loading,
  error,
  onOpenDataset,
  onRefresh,
}) {
  const datasets =
    library?.datasets ?? [];

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
            Reopen your latest dataset
            versions without uploading
            them again.
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

            return (
              <article
                key={dataset.id}
                className="dataset-library-item"
              >
                <div>
                  <h3>
                    {dataset.name}
                  </h3>

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
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
