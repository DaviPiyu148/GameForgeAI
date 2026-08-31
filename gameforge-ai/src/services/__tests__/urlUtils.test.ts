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

// --- Direct Local Dev & Production REST/SSE URL joining tests ---
console.log('\n=== Direct API Base & Endpoint Joining Tests ===\n');

assert(
  'getApiBaseUrl: undefined returns relative /api',
  getApiBaseUrl(undefined),
  '/api'
);

assert(
  'getApiBaseUrl: empty string returns relative /api',
  getApiBaseUrl(''),
  '/api'
);

assert(
  'getApiBaseUrl: default 127.0.0.1:8000 normalizes to http://127.0.0.1:8000/api',
  getApiBaseUrl('http://127.0.0.1:8000'),
  'http://127.0.0.1:8000/api'
);

assert(
  'getApiBaseUrl: 127.0.0.1:8000/ with trailing slash normalizes to http://127.0.0.1:8000/api',
  getApiBaseUrl('http://127.0.0.1:8000/'),
  'http://127.0.0.1:8000/api'
);

assert(
  'getApiBaseUrl: 127.0.0.1:8000/api already ending in /api preserves /api without duplication',
  getApiBaseUrl('http://127.0.0.1:8000/api'),
  'http://127.0.0.1:8000/api'
);

assert(
  'getApiBaseUrl: 127.0.0.1:8000/api/ with trailing slash preserves /api',
  getApiBaseUrl('http://127.0.0.1:8000/api/'),
  'http://127.0.0.1:8000/api'
);

assert(
  'getApiBaseUrl: production origin normalizes to https://production-api.example.com/api',
  getApiBaseUrl('https://production-api.example.com'),
  'https://production-api.example.com/api'
);

assert(
  'joinApiUrl + getApiBaseUrl: discovery search has no double /api',
  joinApiUrl(getApiBaseUrl('http://127.0.0.1:8000'), '/discovery/search'),
  'http://127.0.0.1:8000/api/discovery/search'
);

assert(
  'joinApiUrl + getApiBaseUrl: auth me has no double /api',
  joinApiUrl(getApiBaseUrl('http://127.0.0.1:8000'), '/auth/me'),
  'http://127.0.0.1:8000/api/auth/me'
);

assert(
  'joinApiUrl + getApiBaseUrl: profile progress has no double /api',
  joinApiUrl(getApiBaseUrl('http://127.0.0.1:8000'), '/profile/progress'),
  'http://127.0.0.1:8000/api/profile/progress'
);

assert(
  'joinApiUrl + getApiBaseUrl: profile preferences has no double /api',
  joinApiUrl(getApiBaseUrl('http://127.0.0.1:8000'), '/profile/preferences'),
  'http://127.0.0.1:8000/api/profile/preferences'
);

assert(
  'joinApiUrl + getApiBaseUrl: SSE build events URL is direct to backend origin',
  joinApiUrl(getApiBaseUrl('http://127.0.0.1:8000'), `builds/test-build-1/events?sse_token=sample_token_123`),
  'http://127.0.0.1:8000/api/builds/test-build-1/events?sse_token=sample_token_123'
);

assert(
  'joinApiUrl + getApiBaseUrl: custom port 8001 routes discovery search to port 8001',
  joinApiUrl(getApiBaseUrl('http://127.0.0.1:8001'), '/discovery/search'),
  'http://127.0.0.1:8001/api/discovery/search'
);

assert(
  'joinApiUrl + getApiBaseUrl: explicit custom domain is preserved without double /api',
  joinApiUrl(getApiBaseUrl('https://api.customgame.io'), '/projects'),
  'https://api.customgame.io/api/projects'
);

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);
if (failed > 0) {
  if (typeof (globalThis as any).process !== 'undefined') {
    (globalThis as any).process.exit(1);
  } else {
    throw new Error(`${failed} tests failed`);
  }
}

