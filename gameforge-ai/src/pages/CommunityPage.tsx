import React from 'react';
import { Link } from 'react-router-dom';

const CommunityPage: React.FC = () => {
  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 animate-fade-in pb-12">
      {/* Page Header */}
      <header className="border-b border-primary/30 pb-6 space-y-2">
        <div className="flex items-center gap-2 text-primary">
          <span className="material-symbols-outlined text-2xl">groups</span>
          <span className="font-mono text-xs uppercase tracking-widest font-bold">NETWORK // COMMUNITY_HUB</span>
        </div>
        <h1 className="font-display text-2xl md:text-3xl text-white uppercase tracking-wider">
          GameForge AI Community Hub
        </h1>
        <p className="font-mono text-xs sm:text-sm text-on-surface-variant max-w-3xl leading-relaxed">
          Connect, collaborate, and share game designs with indie developers, game artists, and interactive creators worldwide.
        </p>
      </header>

      {/* Status Notice Banner */}
      <section className="bg-terminal-bg border-2 border-secondary/50 rounded-lg p-6 sm:p-8 space-y-4 shadow-xl glow-box-magenta">
        <div className="flex items-center gap-3 text-secondary font-mono text-xs font-bold uppercase">
          <span className="material-symbols-outlined text-xl">schedule</span>
          <span>DEVELOPMENT ROADMAP // STATUS: COMING SOON</span>
        </div>
        <h2 className="font-display text-xl text-white uppercase">Community Features in Active Development</h2>
        <p className="font-body text-xs sm:text-sm text-on-surface-variant max-w-2xl leading-relaxed">
          The GameForge AI social and community infrastructure is currently being architected. Our roadmap focuses on empowering creators to showcase browser prototypes, publish shared discovery packs, and fork game designs openly.
        </p>
      </section>

      {/* Planned Feature Cards */}
      <section className="space-y-4">
        <h3 className="font-display text-lg text-white uppercase tracking-wider flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">dynamic_feed</span>
          Planned Features on the Roadmap
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div className="bg-terminal-bg border border-primary/30 rounded-lg p-6 space-y-3 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold uppercase">
                <span className="material-symbols-outlined text-base">public</span>
                <span>Prototype Showcase</span>
              </div>
              <span className="px-2 py-0.5 bg-primary/10 border border-primary/30 text-primary font-mono text-[9px] uppercase font-bold rounded">
                PLANNED
              </span>
            </div>
            <h4 className="font-display text-base text-white uppercase">Public Playable Galleries</h4>
            <p className="font-body text-xs text-on-surface-variant leading-relaxed">
              Publish generated Phaser 2D prototypes with shareable web links, playtest leaderboards, and real-time community gameplay telemetry.
            </p>
          </div>

          <div className="bg-terminal-bg border border-secondary/30 rounded-lg p-6 space-y-3 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-secondary font-mono text-xs font-bold uppercase">
                <span className="material-symbols-outlined text-base">alt_route</span>
                <span>Open Remix Trees</span>
              </div>
              <span className="px-2 py-0.5 bg-secondary/10 border border-secondary/30 text-secondary font-mono text-[9px] uppercase font-bold rounded">
                PLANNED
              </span>
            </div>
            <h4 className="font-display text-base text-white uppercase">Collaborative Lineage</h4>
            <p className="font-body text-xs text-on-surface-variant leading-relaxed">
              Inspect version histories, branch off community prototypes, and iterate on game mechanics with complete attribution and remix lineage.
            </p>
          </div>

          <div className="bg-terminal-bg border border-tertiary/30 rounded-lg p-6 space-y-3 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-tertiary font-mono text-xs font-bold uppercase">
                <span className="material-symbols-outlined text-base">bookmarks</span>
                <span>Discovery Packs</span>
              </div>
              <span className="px-2 py-0.5 bg-tertiary/10 border border-tertiary/30 text-tertiary font-mono text-[9px] uppercase font-bold rounded">
                PLANNED
              </span>
            </div>
            <h4 className="font-display text-base text-white uppercase">Curated Catalog Collections</h4>
            <p className="font-body text-xs text-on-surface-variant leading-relaxed">
              Curate and share niche game discovery collections, tag filters, and hidden gem recommendations with other players.
            </p>
          </div>

          <div className="bg-terminal-bg border border-emerald-500/30 rounded-lg p-6 space-y-3 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs font-bold uppercase">
                <span className="material-symbols-outlined text-base">military_tech</span>
                <span>Creator Badges</span>
              </div>
              <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-400/30 text-emerald-400 font-mono text-[9px] uppercase font-bold rounded">
                PLANNED
              </span>
            </div>
            <h4 className="font-display text-base text-white uppercase">Progression Recognition</h4>
            <p className="font-body text-xs text-on-surface-variant leading-relaxed">
              Display Creator XP milestones, synthesis mastery achievements, and discovery badges directly on public creator profiles.
            </p>
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section className="bg-surface-container-low border border-primary/30 rounded-lg p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="space-y-1">
          <h4 className="font-display text-base text-white uppercase">Ready to start prototyping today?</h4>
          <p className="font-mono text-xs text-on-surface-variant">
            Explore the Natural Logic Builder and synthesize your next game concept now.
          </p>
        </div>
        <Link
          to="/build"
          className="px-6 py-2.5 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan"
        >
          Launch Builder
        </Link>
      </section>
    </div>
  );
};

export default CommunityPage;
