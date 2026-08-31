/**
 * URL joining and API base resolution utilities for GameForge AI services.
 *
 * Problem (FS-028 & Remediation V1):
 * 1. Concatenating API_BASE_URL with a path using simple checks produces double-slashes
 *    when the configured base ends with a slash (e.g. "http://127.0.0.1:8000/api/").
 * 2. When VITE_API_URL is configured as a direct backend origin without "/api"
 *    (e.g. "http://127.0.0.1:8000"), endpoints must be prefixed with "/api" to route
 *    to FastAPI's mounted API routers.
 *
 * Solution:
 * - `getApiBaseUrl()` normalizes the environment variable so it consistently ends in "/api".
 * - `joinApiUrl()` ensures exactly one slash between base and path segments.
 */

/**
 * Helper to safely extract VITE_API_URL in browser or Node test runner environments.
 */
function getEnvApiUrl(): string | undefined {
  if (typeof import.meta !== 'undefined' && import.meta.env) {
    return import.meta.env.VITE_API_URL as string | undefined;
  }
  return undefined;
}

/**
 * Resolves the canonical API base URL from the environment or falls back to relative "/api".
 * If VITE_API_URL is provided as a host origin (e.g. "http://127.0.0.1:8000"), normalizes to ".../api".
 */
export function getApiBaseUrl(envOverride?: string): string {
  const envUrl = (envOverride !== undefined ? envOverride : getEnvApiUrl())?.trim();
  if (!envUrl) {
    return '/api';
  }
  // Strip trailing slash
  const clean = envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl;
  // If base does not already end in "/api", append it
  if (!clean.endsWith('/api')) {
    return `${clean}/api`;
  }
  return clean;
}

/**
 * Joins an API base URL with a path segment, ensuring exactly one slash
 * between them regardless of whether the base has a trailing slash.
 *
 * @param base - The API base URL, e.g. "/api" or "http://127.0.0.1:8000/api"
 * @param path - The path segment, e.g. "builds/1/events" or "/builds/1/events"
 * @returns The combined URL with exactly one slash between base and path.
 */
export function joinApiUrl(base: string, path: string): string {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base;
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
  return `${normalizedBase}/${normalizedPath}`;
}

/**
 * Resolves the canonical Swagger / OpenAPI interactive documentation URL.
 * FastAPI serves Swagger at `/docs` relative to the root backend origin.
 *
 * In local development with Vite proxy (no VITE_API_URL or relative "/api"),
 * returns relative "/docs" which routes through the Vite proxy to FastAPI backend.
 *
 * In configured environments with an absolute origin, resolves to the backend root + "/docs".
 *
 * Examples:
 * - Direct host origin "http://127.0.0.1:8000" -> "http://127.0.0.1:8000/docs"
 * - API path "http://127.0.0.1:8000/api" -> "http://127.0.0.1:8000/docs"
 * - Deployed API "https://api.example.com/api" -> "https://api.example.com/docs"
 * - Relative default "" or "/api" -> "/docs" (handled via proxy in dev / reverse proxy in prod)
 *
 * @param envOverride - Optional string to override import.meta.env.VITE_API_URL for unit testing.
 */
export function getSwaggerDocsUrl(envOverride?: string): string {
  const envUrl = (envOverride !== undefined ? envOverride : getEnvApiUrl())?.trim();
  if (!envUrl || envUrl.startsWith('/')) {
    return '/docs';
  }
  // If absolute URL, strip trailing "/api" or slashes to get the root backend origin
  let root = envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl;
  if (root.endsWith('/api')) {
    root = root.slice(0, -4);
  }
  return joinApiUrl(root, '/docs');
}


