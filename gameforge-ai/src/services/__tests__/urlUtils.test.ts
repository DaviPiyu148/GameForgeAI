/**
 * Unit tests for joinApiUrl (FS-028 regression coverage).
 *
 * Run with: npx tsx src/services/__tests__/urlUtils.test.ts
 * (tsx is available via vite's own dep resolution, or install standalone)
 *
 * These tests validate that joinApiUrl never produces double-slash URLs
 * regardless of whether API_BASE_URL has a trailing slash.
 */

import { joinApiUrl, getSwaggerDocsUrl, getApiBaseUrl } from '../urlUtils';

let passed = 0;
let failed = 0;

function assert(label: string, actual: string, expected: string) {
  if (actual === expected) {
    console.log(`  ✓ ${label}`);
    passed++;
  } else {
    console.error(`  ✗ ${label}`);
    console.error(`      Expected: ${expected}`);
    console.error(`      Actual:   ${actual}`);
    failed++;
  }
}

console.log('\n=== joinApiUrl — FS-028 URL normalization tests ===\n');

// --- Relative base URL (dev proxy) ---
assert(
  'relative base without trailing slash',
  joinApiUrl('/api', 'builds/123/events?sse_token=abc'),
  '/api/builds/123/events?sse_token=abc'
);

assert(
  'relative base WITH trailing slash (was double-slash bug)',
  joinApiUrl('/api/', 'builds/123/events?sse_token=abc'),
  '/api/builds/123/events?sse_token=abc'
);

// --- Absolute base URL ---
assert(
  'absolute base without trailing slash',
  joinApiUrl('http://127.0.0.1:8000/api', 'builds/123/events?sse_token=abc'),
  'http://127.0.0.1:8000/api/builds/123/events?sse_token=abc'
);

assert(
  'absolute base WITH trailing slash (was double-slash bug)',
  joinApiUrl('http://127.0.0.1:8000/api/', 'builds/123/events?sse_token=abc'),
  'http://127.0.0.1:8000/api/builds/123/events?sse_token=abc'
);

// --- Edge cases ---
assert(
  'path with leading slash (defensive)',
  joinApiUrl('/api', '/builds/123/events'),
  '/api/builds/123/events'
);

assert(
  'base trailing + path leading slash (no double slash)',
  joinApiUrl('/api/', '/builds/123/events'),
  '/api/builds/123/events'
);

assert(
  'empty path segment',
  joinApiUrl('/api', ''),
  '/api/'
);

// --- SSE token query string preservation ---
const token = 'eyJhbGciOiJIUzI1NiJ9.test.sig';
const tokenParam = `?sse_token=${encodeURIComponent(token)}`;
assert(
  'SSE token query string preserved',
  joinApiUrl('/api', `builds/abc-123/events${tokenParam}`),
  `/api/builds/abc-123/events${tokenParam}`
);

// --- Swagger Docs URL derivation tests (DEF-001 regression coverage) ---
console.log('\n=== getSwaggerDocsUrl — DEF-001 Swagger resolution tests ===\n');

assert(
  'getSwaggerDocsUrl: undefined VITE_API_URL returns relative /docs for Vite dev proxy',
  getSwaggerDocsUrl(undefined),
  '/docs'
);

assert(
  'getSwaggerDocsUrl: empty string returns relative /docs',
  getSwaggerDocsUrl(''),
  '/docs'
);

assert(
  'getSwaggerDocsUrl: relative /api returns relative /docs',
  getSwaggerDocsUrl('/api'),
  '/docs'
);

assert(
  'getSwaggerDocsUrl: root origin without /api resolves to /docs',
  getSwaggerDocsUrl('http://127.0.0.1:8000'),
  'http://127.0.0.1:8000/docs'
);

assert(
  'getSwaggerDocsUrl: root origin with /api resolves to /docs',
  getSwaggerDocsUrl('http://127.0.0.1:8000/api'),
  'http://127.0.0.1:8000/docs'
);

assert(
  'getSwaggerDocsUrl: root origin with /api/ trailing slash resolves to /docs',
  getSwaggerDocsUrl('http://127.0.0.1:8000/api/'),
  'http://127.0.0.1:8000/docs'
);

assert(
  'getSwaggerDocsUrl: production origin resolves to /docs',
  getSwaggerDocsUrl('https://api.gameforge.ai'),
  'https://api.gameforge.ai/docs'
);

assert(
  'getSwaggerDocsUrl: production origin with /api resolves to /docs',
  getSwaggerDocsUrl('https://api.gameforge.ai/api'),
  'https://api.gameforge.ai/docs'
);

assert(
  'getSwaggerDocsUrl: production origin with /api/ trailing slash resolves to /docs',
  getSwaggerDocsUrl('https://api.gameforge.ai/api/'),
  'https://api.gameforge.ai/docs'
);

// --- Overridden BACKEND_PORT tests ---
assert(
  'getSwaggerDocsUrl: custom overridden port 8001 resolves to /docs',
  getSwaggerDocsUrl('http://127.0.0.1:8001'),
  'http://127.0.0.1:8001/docs'
);

assert(
  'getSwaggerDocsUrl: custom overridden port 8001/api resolves to /docs',
  getSwaggerDocsUrl('http://127.0.0.1:8001/api'),
  'http://127.0.0.1:8001/docs'
);

assert(
  'getApiBaseUrl: custom overridden port 8001 normalizes to /api',
  getApiBaseUrl('http://127.0.0.1:8001'),
  'http://127.0.0.1:8001/api'
);

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);
if (failed > 0) {
  if (typeof (globalThis as any).process !== 'undefined') {
    (globalThis as any).process.exit(1);
  } else {
    throw new Error(`${failed} tests failed`);
  }
}

