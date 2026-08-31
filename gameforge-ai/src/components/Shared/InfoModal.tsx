import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useAppContext } from '../../context/AppContext';

export type InfoModalTab = 'docs' | 'api' | 'community' | 'support' | 'privacy';

export const InfoModal: React.FC = () => {
  const { state, openInfoModal, closeInfoModal } = useAppContext();
  const activeTab: InfoModalTab = state.infoModalTab || 'docs';

  // Lock body scroll while modal is open
  useEffect(() => {
    if (state.infoModalTab) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [state.infoModalTab]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && state.infoModalTab) {
        closeInfoModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state.infoModalTab, closeInfoModal]);

  if (!state.infoModalTab) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm modal-backdrop-enter"
      role="dialog"
      aria-modal="true"
      aria-label="Information and Documentation Dialog"
      onClick={(e) => {
        if (e.target === e.currentTarget) closeInfoModal();
      }}
    >
      <div
        className="w-full max-w-4xl max-h-[90vh] bg-surface border-2 border-primary shadow-[0_0_30px_rgba(76,224,210,0.25)] flex flex-col rounded-sm modal-enter relative z-10 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Terminal Header */}
        <div className="bg-terminal-header border-b border-primary/30 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-base">terminal</span>
            <span className="font-mono text-xs text-primary uppercase tracking-wider font-bold">
              GAMEFORGE_INTEL // {activeTab.toUpperCase()}
            </span>
          </div>
          <button
            onClick={closeInfoModal}
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
            aria-label="Close information dialog"
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="bg-terminal-bg border-b border-primary/20 px-4 pt-3 flex flex-wrap gap-2">
          {[
            { id: 'docs' as const, label: 'Documentation', icon: 'menu_book' },
            { id: 'api' as const, label: 'API Access', icon: 'api' },
            { id: 'community' as const, label: 'Community', icon: 'groups' },
            { id: 'support' as const, label: 'Support', icon: 'support_agent' },
            { id: 'privacy' as const, label: 'Privacy Policy', icon: 'shield' },
          ].map((tab) => {
            const isSelected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => openInfoModal(tab.id)}
                className={`px-3 py-2 font-mono text-xs uppercase tracking-wider transition-all flex items-center gap-1.5 cursor-pointer rounded-t-sm ${
                  isSelected
                    ? 'bg-primary text-on-primary font-bold shadow-[0_0_10px_rgba(76,224,210,0.3)]'
                    : 'bg-surface-container-low text-on-surface-variant hover:text-primary hover:bg-surface-container'
                }`}
              >
                <span className="material-symbols-outlined text-sm">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Modal Body Content */}
        <div className="flex-1 overflow-y-auto p-6 bg-terminal-bg space-y-6 font-mono text-xs text-on-surface leading-relaxed">
          {/* TAB 1: DOCUMENTATION */}
          {activeTab === 'docs' && (
            <div className="space-y-6 animate-fade-in">
              <div>
                <h3 className="font-display text-lg text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">menu_book</span>
                  Platform Architecture & Concepts
                </h3>
                <p className="text-on-surface-variant">
                  GameForge AI is an end-to-end platform for AI-powered game discovery and real-time playable prototyping. It pairs vector-based semantic catalog matching with a deterministic Phaser 2D compiler.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-surface-container-low border border-primary/20 rounded">
                  <h4 className="font-bold text-primary mb-1 uppercase flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">tune</span>
                    Natural Logic Builder
                  </h4>
                  <p className="text-on-surface-variant text-[11px]">
                    Transforms natural language design prompts into structured GameDSL schemas. Configurable world modes include Linear, Multi-Stage Campaign, and Open-World topologies.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded">
                  <h4 className="font-bold text-secondary mb-1 uppercase flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">search</span>
                    Multi-Signal Discovery
                  </h4>
                  <p className="text-on-surface-variant text-[11px]">
                    Dense semantic embeddings powered by SentenceTransformers paired with FAISS indexing. Supports negative filters, session tuning, and diversity reranking.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded">
                  <h4 className="font-bold text-tertiary mb-1 uppercase flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">dna</span>
                    Dynamic Game DNA
                  </h4>
                  <p className="text-on-surface-variant text-[11px]">
                    User profile preference modeling tracking genres, playstyles, and avoidances to provide progressively calibrated recommendations without overfitting.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded">
                  <h4 className="font-bold text-emerald-400 mb-1 uppercase flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">videogame_asset</span>
                    Phaser 2D Runtime
                  </h4>
                  <p className="text-on-surface-variant text-[11px]">
                    Strictly typed schema validation ensures generated prototypes run safely in standard WebGL/Canvas environments with zero arbitrary code execution.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: API ACCESS */}
          {activeTab === 'api' && (
            <div className="space-y-6 animate-fade-in">
              <div>
                <h3 className="font-display text-lg text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">api</span>
                  API Access & Developer Interface
                </h3>
                <p className="text-on-surface-variant">
                  GameForge AI exposes a structured REST API and Server-Sent Events (SSE) streaming protocol built on FastAPI.
                </p>
              </div>

              <div className="space-y-4">
                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-2">
                  <h4 className="font-bold text-primary uppercase">Authentication & Credentials</h4>
                  <p className="text-on-surface-variant text-[11px]">
                    Authenticated endpoints require an HTTP Authorization header formatted as <code className="text-primary">Bearer &lt;token&gt;</code>. Authentication tokens are issued via <code className="text-primary">POST /api/auth/login</code> and <code className="text-primary">POST /api/auth/register</code>.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-2">
                  <h4 className="font-bold text-secondary uppercase">Ephemeral SSE Tokens</h4>
                  <p className="text-on-surface-variant text-[11px]">
                    Build compilation telemetry streams over SSE using single-purpose credentials (<code className="text-secondary">POST /api/builds/&#123;id&#125;/sse-token</code>) with 90-second expiration, protecting your primary JWT token.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-2">
                  <h4 className="font-bold text-white uppercase">Interactive Documentation</h4>
                  <p className="text-on-surface-variant text-[11px]">
                    Explore the complete OpenAPI 3.1 specification, request schemas, and try out live endpoints directly in the Swagger UI:
                  </p>
                  <div className="pt-2">
                    <a
                      href="http://127.0.0.1:8000/docs"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary/20 border border-primary text-primary hover:bg-primary/30 rounded font-bold transition-all"
                    >
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                      <span>Launch Swagger UI (/docs)</span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: COMMUNITY */}
          {activeTab === 'community' && (
            <div className="space-y-6 animate-fade-in">
              <div>
                <h3 className="font-display text-lg text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">groups</span>
                  Creator Community
                </h3>
                <p className="text-on-surface-variant">
                  Join creators, indie developers, and game designers building next-generation prototypes with GameForge AI.
                </p>
              </div>

              <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-3">
                <div className="flex items-center gap-2 text-secondary font-bold">
                  <span className="material-symbols-outlined">schedule</span>
                  <span>COMMUNITY HUB COMING SOON</span>
                </div>
                <p className="text-on-surface-variant text-[11px]">
                  Upcoming community features include public prototype showcase galleries, community game remix trees, collaborative discovery packs, and creator leaderboard rankings.
                </p>
                <div className="pt-2 border-t border-outline-variant/30 text-[11px] text-on-surface-variant">
                  For development inquiries and source contributions, visit our repository.
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: SUPPORT */}
          {activeTab === 'support' && (
            <div className="space-y-6 animate-fade-in">
              <div>
                <h3 className="font-display text-lg text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">support_agent</span>
                  Support & Diagnostics
                </h3>
                <p className="text-on-surface-variant">
                  Need assistance or experiencing unexpected behavior? Follow our diagnostic checklist below.
                </p>
              </div>

              <div className="space-y-4">
                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-2">
                  <h4 className="font-bold text-primary uppercase">Quick Troubleshooting</h4>
                  <ul className="list-disc list-inside space-y-1 text-[11px] text-on-surface-variant">
                    <li><strong className="text-white">API Connection:</strong> Ensure the FastAPI backend is running on port 8000 (<code className="text-primary">GET /api/health</code>).</li>
                    <li><strong className="text-white">Vite Proxy:</strong> For direct backend communication, set <code className="text-primary">VITE_API_URL=http://127.0.0.1:8000</code> in your environment.</li>
                    <li><strong className="text-white">Compiler Logs:</strong> Use the "COPY OUTPUT" button in Builder or Build Status to capture complete diagnostic traces.</li>
                  </ul>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-2">
                  <h4 className="font-bold text-white uppercase">Reporting Issues</h4>
                  <p className="text-on-surface-variant text-[11px]">
                    When submitting bug reports, please include your browser version, viewport resolution, relevant compiler logs, and request ID headers from API error envelopes.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: PRIVACY POLICY */}
          {activeTab === 'privacy' && (
            <div className="space-y-6 animate-fade-in">
              <div>
                <h3 className="font-display text-lg text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">shield</span>
                  Privacy & Data Policy
                </h3>
                <p className="text-on-surface-variant">
                  We believe in transparency, user privacy, and zero unnecessary data collection.
                </p>
              </div>

              <div className="space-y-4 text-[11px] text-on-surface-variant">
                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-1.5">
                  <h4 className="font-bold text-primary uppercase">Local Data Storage</h4>
                  <p>
                    All project data, prototypes, and Game DNA preferences are stored locally in the SQLite database (<code className="text-primary">gameforge.db</code>). You maintain full ownership over your projects and configurations.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-1.5">
                  <h4 className="font-bold text-secondary uppercase">Authentication & Passwords</h4>
                  <p>
                    Passwords are encrypted using industry-standard Argon2id cryptographic hashing before storage. Passwords and secret credentials are never logged or transmitted in plain text.
                  </p>
                </div>

                <div className="p-4 bg-surface-container-low border border-primary/20 rounded space-y-1.5">
                  <h4 className="font-bold text-tertiary uppercase">No Third-Party Trackers</h4>
                  <p>
                    GameForge AI does not use third-party analytics trackers, advertising cookies, or behavioral data brokers.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-terminal-header border-t border-primary/20 flex justify-end">
          <button
            type="button"
            onClick={closeInfoModal}
            className="px-5 py-2 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
