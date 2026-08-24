/**
 * URL joining utilities for GameForge AI services.
 *
 * Problem (FS-028): Concatenating API_BASE_URL with a path using a simple
 * conditional slash check still produces double-slashes when the configured
 * base already ends with a slash (e.g. "http://127.0.0.1:8000/api/").
 *
 * Solution: Always strip the trailing slash from the base, then join with a
 * single "/"-prefixed path segment.  This is safe for both relative
 * ("/api") and absolute ("http://host/api") bases.
 *
 * Test cases (verified in this file's JSDoc):
 *   joinApiUrl("/api",                      "builds/1/events") → "/api/builds/1/events"
 *   joinApiUrl("/api/",                     "builds/1/events") → "/api/builds/1/events"
 *   joinApiUrl("http://127.0.0.1:8000/api", "builds/1/events") → "http://127.0.0.1:8000/api/builds/1/events"
 *   joinApiUrl("http://127.0.0.1:8000/api/","builds/1/events") → "http://127.0.0.1:8000/api/builds/1/events"
 */

/**
 * Joins an API base URL with a path segment, ensuring exactly one slash
 * between them regardless of whether the base has a trailing slash.
 *
 * @param base - The API base URL, e.g. "/api" or "http://host/api/"
 * @param path - The path segment WITHOUT a leading slash, e.g. "builds/1/events"
 * @returns The combined URL with exactly one slash between base and path.
 */
export function joinApiUrl(base: string, path: string): string {
  // Strip trailing slash from base (handles "/api/" and "http://host/api/")
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base;
  // Strip leading slash from path (defensive; callers should not include it)
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
  return `${normalizedBase}/${normalizedPath}`;
}
