const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000";

const API_BASE_URL = configuredApiBaseUrl
  .trim()
  .replace(/\/+$/, "");

const TOKEN_KEY =
  "signal-ledger-access-token";

export const AUTH_SESSION_EVENT =
  "signal-ledger-auth-session-ended";


function endAuthenticatedSession(
  detail
) {
  clearAccessToken();

  const message =
    detail ===
    "Authentication session expired."
      ? "Your session expired. Please sign in again."
      : "Your session is no longer valid. Please sign in again.";

  window.dispatchEvent(
    new CustomEvent(
      AUTH_SESSION_EVENT,
      {
        detail: {
          message,
        },
      }
    )
  );
}


export function getAccessToken() {
  return sessionStorage.getItem(
    TOKEN_KEY
  );
}


export function setAccessToken(token) {
  if (!token) {
    sessionStorage.removeItem(
      TOKEN_KEY
    );
    return;
  }

  sessionStorage.setItem(
    TOKEN_KEY,
    token
  );
}


export function clearAccessToken() {
  sessionStorage.removeItem(
    TOKEN_KEY
  );
}


export function isAuthenticated() {
  return Boolean(
    getAccessToken()
  );
}


function buildHeaders(
  options = {},
  includeAuth = true
) {
  const headers = new Headers(
    options.headers ?? {}
  );

  if (includeAuth) {
    const token = getAccessToken();

    if (token) {
      headers.set(
        "Authorization",
        `Bearer ${token}`
      );
    }
  }

  return headers;
}


async function request(
  path,
  options = {},
  {
    includeAuth = true,
  } = {}
) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}${path}`,
      {
        ...options,
        headers: buildHeaders(
          options,
          includeAuth
        ),
      }
    );
  } catch {
    throw new Error(
      "The analytics API is unavailable. " +
      "Check that the backend is running."
    );
  }

  const payload =
    await response
      .json()
      .catch(() => ({}));

  if (!response.ok) {
    if (
      response.status === 401 &&
      includeAuth
    ) {
      endAuthenticatedSession(
        payload.detail
      );
    }

    throw new Error(
      payload.detail ||
      "The analytics API returned an error."
    );
  }

  return payload;
}


export async function registerUser(
  email,
  password
) {
  return request(
    "/auth/register",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        email,
        password,
      }),
    },
    {
      includeAuth: false,
    }
  );
}


export async function loginUser(
  email,
  password
) {
  const payload = await request(
    "/auth/login",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify({
        email,
        password,
      }),
    },
    {
      includeAuth: false,
    }
  );

  setAccessToken(
    payload.access_token
  );

  return payload;
}


export function logoutUser() {
  clearAccessToken();
}


export function loadCurrentUser() {
  return request(
    "/auth/me"
  );
}


export function uploadDataset(
  file,
  datasetId = null
) {
  const formData =
    new FormData();

  formData.append(
    "file",
    file
  );

  if (datasetId) {
    formData.append(
      "dataset_id",
      datasetId
    );
  }

  return request(
    "/datasets/upload",
    {
      method: "POST",
      body: formData,
    }
  );
}


export function loadDatasetOverview(
  datasetVersionId
) {
  return Promise.all([
    request(
      `/datasets/${datasetVersionId}/validate`,
      {
        method: "POST",
      }
    ),
    request(
      `/datasets/${datasetVersionId}/pii-scan`,
      {
        method: "POST",
      }
    ),
    request(
      `/datasets/${datasetVersionId}/profile`
    ),
    request(
      `/datasets/${datasetVersionId}/semantics`
    ),
  ]).then(
    ([
      validation,
      pii,
      profile,
      semantics,
    ]) => ({
      validation:
        validation.validation,
      pii:
        pii.pii_scan,
      profile:
        profile.profile,
      semantics:
        semantics.semantics,
    })
  );
}


export function loadDatasetPlan(
  datasetVersionId
) {
  return request(
    `/datasets/${datasetVersionId}/plan`
  ).then(
    (payload) =>
      payload.analytics_plan
  );
}


export function analyzeDataset(
  datasetVersionId
) {
  return request(
    `/datasets/${datasetVersionId}/analyze`,
    {
      method: "POST",
    }
  );
}


export function loadAnalysisRun(
  analysisRunId
) {
  return request(
    `/analysis-runs/${analysisRunId}`
  );
}


export function loadAnalysisRuns(
  datasetVersionId
) {
  return request(
    "/analysis-runs/" +
    `dataset-version/${datasetVersionId}`
  );
}


export async function downloadAnalysisRunExport(
  analysisRunId,
  exportFormat
) {
  const token =
    getAccessToken();

  if (!token) {
    throw new Error(
      "Sign in before exporting reports."
    );
  }

  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}` +
      `/analysis-runs/${analysisRunId}` +
      `/export/${exportFormat}`,
      {
        headers: {
          Authorization:
            `Bearer ${token}`,
        },
      }
    );
  } catch {
    throw new Error(
      "The analytics API is unavailable."
    );
  }

  if (!response.ok) {
    const payload =
      await response
        .json()
        .catch(() => ({}));

    if (response.status === 401) {
      endAuthenticatedSession(
        payload.detail
      );
    }

    throw new Error(
      payload.detail ||
      "Report export failed."
    );
  }

  const blob =
    await response.blob();

  const disposition =
    response.headers.get(
      "Content-Disposition"
    );

  const filenameMatch =
    disposition?.match(
      /filename="?([^"]+)"?/i
    );

  const filename =
    filenameMatch?.[1] ??
    `signal-ledger-report.${exportFormat}`;

  const url =
    URL.createObjectURL(blob);

  const link =
    document.createElement("a");

  link.href = url;
  link.download = filename;

  document.body.appendChild(
    link
  );

  link.click();
  link.remove();

  URL.revokeObjectURL(url);
}


export function listOwnedDatasets() {
  return request(
    "/datasets"
  );
}


export function listDatasetVersions(
  datasetId
) {
  return request(
    `/datasets/${datasetId}/versions`
  );
}
