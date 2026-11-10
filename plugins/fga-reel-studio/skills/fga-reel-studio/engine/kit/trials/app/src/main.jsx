import React from "react";
import { createRoot } from "react-dom/client";
import { PaneApp } from "./pane/PaneApp.jsx";
import "./pane/pane.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <PaneApp />
  </React.StrictMode>,
);

// Remembers a "Trials is off" page, so a reload while the server is down shows a way back instead of an error.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
