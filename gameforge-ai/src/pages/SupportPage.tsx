import React from 'react';
import { Link } from 'react-router-dom';

const SupportPage: React.FC = () => {
  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Page Header */}
      <header className="border-b border-primary/30 pb-6 space-y-2">
        <div className="flex items-center gap-2 text-primary">
          <span className="material-symbols-outlined text-2xl">support_agent</span>
          <span className="font-mono text-xs uppercase tracking-widest font-bold">HELP & DIAGNOSTICS // SUPPORT_V1.0</span>
        </div>
        <h1 className="font-display text-2xl md:text-3xl text-white uppercase tracking-wider">
          GameForge AI Support & Diagnostics
        </h1>
        <p className="font-mono text-xs sm:text-sm text-on-surface-variant max-w-3xl leading-relaxed">
          Diagnostic checklists, system troubleshooting, browser compatibility information, and issue reporting procedures.
        </p>
      </header>

      {/* Troubleshooting Checklist Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Diagnostic 1: API Connectivity */}
        <section className="bg-terminal-bg border border-primary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">cloud_done</span>
            <span>API Connectivity</span>
          </div>
          <h3 className="font-display text-base text-white uppercase">Backend Reachability</h3>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            Ensure the GameForge API service is reachable at the configured backend URL. You can verify backend health by inspecting the health status endpoint (<code className="text-primary">GET /api/health</code>).
          </p>
          <div className="p-3 bg-surface-container-low border border-outline-variant/30 rounded font-mono text-[11px] text-on-surface-variant space-y-1">
            <span className="text-primary font-bold block uppercase text-[10px]">Local Development Note:</span>
            <span>For local development, GameForge can use the bundled FastAPI service running on the default local development API port.</span>
          </div>
        </section>

        {/* Diagnostic 2: Browser Voice Input */}
        <section className="bg-terminal-bg border border-secondary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-secondary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">mic</span>
            <span>Voice Input Compatibility</span>
          </div>
          <h3 className="font-display text-base text-white uppercase">Web Speech Recognition</h3>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            Discovery voice input uses the browser's native Web Speech API. Chrome, Chromium-based browsers, and Edge support this natively. If your browser does not support Web Speech, keyboard text search remains fully functional.
          </p>
          <div className="p-3 bg-surface-container-low border border-outline-variant/30 rounded font-mono text-[11px] text-on-surface-variant space-y-1">
            <span className="text-secondary font-bold block uppercase text-[10px]">Permission Tip:</span>
            <span>Ensure microphone access permissions are allowed in your browser settings if speech transcription does not activate.</span>
          </div>
        </section>

        {/* Diagnostic 3: Compiler Logs & Diagnostics */}
        <section className="bg-terminal-bg border border-tertiary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-tertiary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">terminal</span>
            <span>Compiler Output Export</span>
          </div>
          <h3 className="font-display text-base text-white uppercase">Capturing Diagnostic Traces</h3>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            During scene compilation or on failure screens, use the <strong className="text-white">COPY OUTPUT</strong> button located in the compiler console header to copy raw diagnostic traces to your clipboard.
          </p>
          <div className="p-3 bg-surface-container-low border border-outline-variant/30 rounded font-mono text-[11px] text-on-surface-variant">
            <span>Compiler traces capture validation stages, repair passes, and runtime scene initialization metrics.</span>
          </div>
        </section>

        {/* Diagnostic 4: Phaser WebGL / Canvas */}
        <section className="bg-terminal-bg border border-emerald-500/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">videogame_asset</span>
            <span>Phaser Canvas Rendering</span>
          </div>
          <h3 className="font-display text-base text-white uppercase">Hardware Acceleration</h3>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            Prototypes render in 60 FPS using WebGL with automatic HTML5 2D Canvas fallback. If gameplay experiences low framerates, verify that hardware acceleration is enabled in your browser settings.
          </p>
          <div className="p-3 bg-surface-container-low border border-outline-variant/30 rounded font-mono text-[11px] text-on-surface-variant">
            <span>Fullscreen mode can be toggled in the prototype player to maximize display fidelity.</span>
          </div>
        </section>
      </div>

      {/* Issue Reporting Guidelines */}
      <section className="bg-surface-container-low border border-primary/40 rounded-lg p-6 sm:p-8 space-y-4 shadow-2xl">
        <h2 className="font-display text-xl text-white uppercase tracking-wider flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">bug_report</span>
          Reporting Issues & Bugs
        </h2>
        <p className="font-body text-xs text-on-surface-variant leading-relaxed">
          When reporting an issue, please include the relevant compiler output, prompt parameters, browser version, and OS environment.
        </p>

        <div className="p-4 bg-terminal-bg border border-error/40 rounded space-y-2 text-xs font-mono">
          <div className="flex items-center gap-2 text-error font-bold uppercase">
            <span className="material-symbols-outlined text-base">security</span>
            <span>Security & Privacy Reminder</span>
          </div>
          <p className="text-on-surface-variant text-[11px] leading-relaxed">
            Never submit passwords, JWT bearer tokens, API keys, or private environment variables in issue reports or public tickets. All necessary diagnostic details are present in compiler traces without credentials.
          </p>
        </div>

        <div className="pt-2 flex flex-wrap gap-4 items-center">
          <Link
            to="/documentation"
            className="px-6 py-2.5 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan"
          >
            Review System Manual
          </Link>
          <Link
            to="/api-access"
            className="px-6 py-2.5 border border-primary/50 text-primary hover:bg-primary/10 font-mono text-xs font-bold uppercase rounded btn-interactive"
          >
            Inspect API Specification →
          </Link>
        </div>
      </section>
    </div>
  );
};

export default SupportPage;
