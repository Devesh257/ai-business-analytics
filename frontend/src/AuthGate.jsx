import {
  useEffect,
  useState,
} from "react";

import {
  getAccessToken,
  loadCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "./api";


export default function AuthGate({
  children,
}) {
  const [user, setUser] =
    useState(null);

  const [mode, setMode] =
    useState("login");

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(
      Boolean(getAccessToken())
    );

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      if (!getAccessToken()) {
        setLoading(false);
        return;
      }

      try {
        const currentUser =
          await loadCurrentUser();

        if (!cancelled) {
          setUser(currentUser);
        }
      } catch {
        logoutUser();

        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);


  async function handleSubmit(
    event
  ) {
    event.preventDefault();

    const normalizedEmail =
      email.trim();

    if (!normalizedEmail) {
      setError(
        "Enter your email address."
      );
      return;
    }

    if (!password) {
      setError(
        "Enter your password."
      );
      return;
    }

    if (
      mode === "register" &&
      password.length < 12
    ) {
      setError(
        "Password must contain at least 12 characters."
      );
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await registerUser(
          normalizedEmail,
          password
        );
      }

      await loginUser(
        normalizedEmail,
        password
      );

      const currentUser =
        await loadCurrentUser();

      setUser(currentUser);
      setPassword("");
    } catch (nextError) {
      logoutUser();
      setUser(null);

      setError(
        nextError.message
      );
    } finally {
      setLoading(false);
    }
  }


  function handleLogout() {
    logoutUser();
    setUser(null);
    setPassword("");
    setError("");
  }


  if (loading && !user) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <p className="eyebrow">
            Signal Ledger
          </p>

          <h1>
            Restoring secure session
          </h1>

          <p>
            Verifying your account…
          </p>
        </section>
      </main>
    );
  }


  if (!user) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div>
            <p className="eyebrow">
              Signal Ledger
            </p>

            <h1>
              {mode === "login"
                ? "Sign in"
                : "Create your account"}
            </h1>

            <p className="auth-intro">
              Your datasets and analysis
              runs are isolated to your
              authenticated account.
            </p>
          </div>

          <form
            className="auth-form"
            onSubmit={handleSubmit}
          >
            <label>
              Email

              <input
                type="email"
                value={email}
                autoComplete="email"
                required
                onChange={(event) =>
                  setEmail(
                    event.target.value
                  )
                }
              />
            </label>

            <label>
              Password

              <input
                type="password"
                value={password}
                autoComplete={
                  mode === "login"
                    ? "current-password"
                    : "new-password"
                }
                minLength={
                  mode === "register"
                    ? 12
                    : undefined
                }
                required
                onChange={(event) =>
                  setPassword(
                    event.target.value
                  )
                }
              />
            </label>

            {mode === "register" && (
              <small>
                Minimum 12 characters.
              </small>
            )}

            {error && (
              <div
                className="notice danger"
                role="alert"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
            >
              {loading
                ? "Please wait…"
                : mode === "login"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>

          <button
            type="button"
            className="auth-switch"
            onClick={() => {
              setMode(
                mode === "login"
                  ? "register"
                  : "login"
              );
              setError("");
              setPassword("");
            }}
          >
            {mode === "login"
              ? "Need an account? Create one"
              : "Already registered? Sign in"}
          </button>
        </section>
      </main>
    );
  }


  return children({
    user,
    logout: handleLogout,
  });
}
