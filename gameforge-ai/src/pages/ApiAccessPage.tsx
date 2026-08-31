import React from 'react';
import { getSwaggerDocsUrl } from '../services/urlUtils';

const ApiAccessPage: React.FC = () => {
  const swaggerUrl = getSwaggerDocsUrl();

  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Page Header */}
      <header className="border-b border-primary/30 pb-6 space-y-2">
        <div className="flex items-center gap-2 text-primary">
          <span className="material-symbols-outlined text-2xl">api</span>
          <span className="font-mono text-xs uppercase tracking-widest font-bold">DEVELOPER INTERFACE // API_V1.0</span>
        </div>
        <h1 className="font-display text-2xl md:text-3xl text-white uppercase tracking-wider">
          GameForge AI API Access
        </h1>
        <p className="font-mono text-xs sm:text-sm text-on-surface-variant max-w-3xl leading-relaxed">
          The GameForge AI backend provides a modular REST API and Server-Sent Events (SSE) streaming infrastructure powered by FastAPI.
        </p>
      </header>

      {/* OpenAPI Swagger Interactive Card */}
      <section className="bg-terminal-bg border-2 border-primary/60 rounded-lg p-6 sm:p-8 space-y-4 shadow-2xl glow-box-cyan">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold uppercase">
              <span className="material-symbols-outlined text-base">terminal</span>
              <span>Interactive OpenAPI 3.1 Specification</span>
            </div>
            <h2 className="font-display text-xl text-white uppercase">Live Swagger UI Explorer</h2>
            <p className="font-mono text-xs text-on-surface-variant max-w-xl">
              Inspect all endpoints, schemas, request payloads, and execute live queries directly via the interactive Swagger documentation.
            </p>
          </div>

          <a
            href={swaggerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan flex items-center gap-2 shrink-0 cursor-pointer"
          >
            <span>Launch Swagger UI</span>
            <span className="material-symbols-outlined text-sm">open_in_new</span>
          </a>
        </div>
      </section>

      {/* Authentication & Security Architecture */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-terminal-bg border border-primary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">key</span>
            <span>JWT Bearer Authentication</span>
          </div>
          <h3 className="font-display text-base text-white uppercase">User Session Tokens</h3>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            Authenticated endpoints require an HTTP Authorization header containing a signed JSON Web Token issued upon login or registration. Passwords are securely hashed with Argon2id prior to database persistence.
          </p>
          <div className="p-3 bg-surface-container-low border border-primary/20 rounded font-mono text-[11px] text-primary">
            Authorization: Bearer &lt;jwt_access_token&gt;
          </div>
        </section>

        <section className="bg-terminal-bg border border-secondary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-secondary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">stream</span>
            <span>Ephemeral SSE Credentials</span>
          </div>
          <h3 className="font-display text-base text-white uppercase">Real-Time Build Streaming</h3>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            Build telemetry streams over Server-Sent Events using single-purpose tokens issued via <code className="text-secondary">POST /api/builds/&#123;id&#125;/sse-token</code> with a strict 90-second time-to-live, protecting your primary JWT session token.
          </p>
          <div className="p-3 bg-surface-container-low border border-secondary/20 rounded font-mono text-[11px] text-secondary">
            GET /api/builds/&#123;id&#125;/events?sse_token=&lt;ephemeral_token&gt;
          </div>
        </section>
      </div>

      {/* Major API Endpoints Surface */}
      <section className="bg-terminal-bg border border-outline-variant/50 rounded-lg p-6 space-y-4 shadow-xl">
        <h3 className="font-display text-lg text-white uppercase tracking-wider flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">hub</span>
          Core API Domains
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
          <div className="p-4 bg-surface-container-low border border-outline-variant/40 rounded space-y-2">
            <div className="font-mono text-xs text-primary font-bold uppercase">Discovery Engine</div>
            <ul className="space-y-1 font-mono text-[11px] text-on-surface-variant">
              <li><code className="text-white">POST</code> /api/discovery/search</li>
              <li><code className="text-white">POST</code> /api/discovery/feedback</li>
              <li><code className="text-white">GET</code> /api/discovery/compare</li>
              <li><code className="text-white">POST</code> /api/discovery/onboard</li>
            </ul>
          </div>

          <div className="p-4 bg-surface-container-low border border-outline-variant/40 rounded space-y-2">
            <div className="font-mono text-xs text-secondary font-bold uppercase">Builds & Compiler</div>
            <ul className="space-y-1 font-mono text-[11px] text-on-surface-variant">
              <li><code className="text-white">POST</code> /api/builds</li>
              <li><code className="text-white">GET</code> /api/builds/&#123;id&#125;</li>
              <li><code className="text-white">POST</code> /api/builds/&#123;id&#125;/sse-token</li>
              <li><code className="text-white">GET</code> /api/builds/&#123;id&#125;/events</li>
            </ul>
          </div>

          <div className="p-4 bg-surface-container-low border border-outline-variant/40 rounded space-y-2">
            <div className="font-mono text-xs text-tertiary font-bold uppercase">Projects & Remix</div>
            <ul className="space-y-1 font-mono text-[11px] text-on-surface-variant">
              <li><code className="text-white">GET</code> /api/projects</li>
              <li><code className="text-white">POST</code> /api/projects</li>
              <li><code className="text-white">GET</code> /api/projects/&#123;id&#125;/blueprint</li>
              <li><code className="text-white">POST</code> /api/projects/&#123;id&#125;/remix</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Deployment & Environment Configuration */}
      <section className="bg-surface-container-low border border-primary/30 rounded-lg p-6 space-y-3">
        <h3 className="font-display text-base text-white uppercase tracking-wider flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">settings_ethernet</span>
          Environment Configuration
        </h3>
        <p className="font-body text-xs text-on-surface-variant leading-relaxed">
          The frontend automatically resolves the API base URL from the <code className="text-primary">VITE_API_URL</code> environment variable. If unspecified, it defaults to the relative <code className="text-primary">/api</code> origin.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 font-mono text-xs">
          <div className="p-3 bg-terminal-bg border border-outline-variant/40 rounded space-y-1">
            <span className="text-on-surface-variant block text-[10px] uppercase">Default Local Routing:</span>
            <span className="text-white">VITE_API_URL=&quot;&quot; (proxies /api to backend)</span>
          </div>
          <div className="p-3 bg-terminal-bg border border-outline-variant/40 rounded space-y-1">
            <span className="text-on-surface-variant block text-[10px] uppercase">Deployed Dedicated Origin:</span>
            <span className="text-white">VITE_API_URL=https://api.yourdomain.com</span>
          </div>
        </div>
      </section>
    </div>
  );
};

export default ApiAccessPage;
