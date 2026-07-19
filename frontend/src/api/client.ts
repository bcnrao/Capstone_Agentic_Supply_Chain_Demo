import axios from "axios";

// Base URL of the FastAPI service. Defaults to same-origin /api (nginx or Vite
// dev proxy forwards to the backend). Override VITE_API_BASE_URL only for a
// split-host deployment (e.g. https://api.example.com).
function normalizeBaseUrl(raw: string | undefined): string {
  const value = (raw ?? "/api").trim();
  return value.replace(/\/+$/, "") || "/api";
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

export const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 120000,
});
