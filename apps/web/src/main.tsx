import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

// Dhan apps registered with the site root return here. Forward the one-time
// code to the server route, where the signed consent cookie is verified.
const consentToken = new URLSearchParams(window.location.search).get("tokenId");
if (consentToken && window.location.pathname === "/") {
  window.location.replace(`/api/v1/dhan/callback?tokenId=${encodeURIComponent(consentToken)}`);
} else {
  createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
}
