import React from 'react';

const PrivacyPage: React.FC = () => {
  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Page Header */}
      <header className="border-b border-primary/30 pb-6 space-y-2">
        <div className="flex items-center gap-2 text-primary">
          <span className="material-symbols-outlined text-2xl">shield</span>
          <span className="font-mono text-xs uppercase tracking-widest font-bold">DATA GOVERNANCE // PRIVACY_V1.0</span>
        </div>
        <h1 className="font-display text-2xl md:text-3xl text-white uppercase tracking-wider">
          GameForge AI Privacy Policy
        </h1>
        <p className="font-mono text-xs text-on-surface-variant">
          Last Updated: August 31, 2026
        </p>
      </header>

      {/* Policy Sections Grid */}
      <div className="space-y-6">
        {/* Section 1: Overview & Scope */}
        <section className="bg-terminal-bg border border-primary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">info</span>
            <span>1. Overview & Architecture Scope</span>
          </div>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            This policy describes how GameForge AI handles user accounts, game discovery telemetry, and generated prototype data. In its current self-hosted architecture, GameForge AI stores application data in a local SQLite database with zero third-party behavioral tracking.
          </p>
        </section>

        {/* Section 2: Authentication & Password Security */}
        <section className="bg-terminal-bg border border-secondary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-secondary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">lock</span>
            <span>2. Authentication & Password Security</span>
          </div>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            User authentication uses industry-standard cryptographic practices. Passwords are securely hashed using Argon2id with unique cryptographic salts before database persistence. Passwords and credentials are never stored, transmitted, or logged in plain text.
          </p>
        </section>

        {/* Section 3: Data Stored in Local Database */}
        <section className="bg-terminal-bg border border-tertiary/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-tertiary font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">database</span>
            <span>3. Persistent Data Storage</span>
          </div>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            The following data is maintained in the application database (<code className="text-tertiary">gameforge.db</code>):
          </p>
          <ul className="list-disc list-inside space-y-1.5 font-mono text-xs text-on-surface-variant pl-2">
            <li><strong className="text-white">User Accounts:</strong> Username, email address, hashed password, created timestamps, and avatar identifiers.</li>
            <li><strong className="text-white">Game Projects:</strong> User prompts, GameDSL schemas, version history, and compilation status.</li>
            <li><strong className="text-white">Game DNA & Preferences:</strong> Calibrated genre preferences, playstyles, and explicit avoidance tags.</li>
            <li><strong className="text-white">Saved Discoveries:</strong> Game catalog bookmarks saved to your profile.</li>
            <li><strong className="text-white">Creator Progress:</strong> Server-authoritative XP balance, current level, and unlocked milestone badges.</li>
          </ul>
        </section>

        {/* Section 4: AI Generation Safety & Prompts */}
        <section className="bg-terminal-bg border border-emerald-500/30 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">psychology</span>
            <span>4. AI Prompt Processing & Safety</span>
          </div>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            Natural language design prompts submitted to the Builder or Discovery engine are processed to derive structured game specifications. The system enforces strict Pydantic schema validation on all model responses prior to browser execution.
          </p>
        </section>

        {/* Section 5: Analytics & Third-Party Trackers */}
        <section className="bg-terminal-bg border border-outline-variant/50 rounded-lg p-6 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-white font-mono text-xs font-bold uppercase">
            <span className="material-symbols-outlined text-base">visibility_off</span>
            <span>5. Zero Third-Party Advertising Trackers</span>
          </div>
          <p className="font-body text-xs text-on-surface-variant leading-relaxed">
            GameForge AI does not embed third-party advertising cookies, external tracking pixels, or cross-site behavioral beacons. All session data remains confined to your configured instance.
          </p>
        </section>
      </div>
    </div>
  );
};

export default PrivacyPage;
