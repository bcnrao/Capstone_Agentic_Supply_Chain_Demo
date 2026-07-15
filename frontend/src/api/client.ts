import axios from "axios";

// Base URL of the FastAPI service. Configured via VITE_API_BASE_URL at build
// time; falls back to the local API port when unset.
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 120000,
});
