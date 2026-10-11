import {
  StrictMode,
} from "react";

import {
  createRoot,
} from "react-dom/client";

import App from "./App.jsx";
import AuthGate from "./AuthGate.jsx";
import "./styles.css";


createRoot(
  document.getElementById("root")
).render(
  <StrictMode>
    <AuthGate>
      {({
        user,
        logout,
      }) => (
        <App
          currentUser={user}
          onLogout={logout}
        />
      )}
    </AuthGate>
  </StrictMode>
);
