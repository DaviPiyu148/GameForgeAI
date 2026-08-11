import { Link } from 'react-router-dom';

const NoMatchesPage = () => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-6 w-full">
      <div className="max-w-2xl w-full mx-auto">
        {/* Terminal Container */}
        <div className="w-full shadow-2xl">
          {/* Terminal Header */}
          <div className="bg-terminal-header h-8 px-4 flex items-center justify-between border-t border-x border-outline-variant rounded-t-md">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-secondary-container inline-block" />
              <span className="w-3 h-3 rounded-full bg-tertiary-container inline-block" />
              <span className="w-3 h-3 rounded-full bg-primary inline-block" />
            </div>
            <span className="font-mono text-[10px] text-on-surface-variant tracking-wider">
              discovery_engine.exe
            </span>
          </div>

          {/* Terminal Body */}
          <div className="bg-terminal-bg border border-outline-variant p-8 flex flex-col items-center text-center rounded-b-md">
            {/* Large Icon Box */}
            <div className="relative w-24 h-24 border-2 border-outline-variant flex items-center justify-center bg-surface/50 mb-6">
              {/* Corner markers */}
              <span className="absolute -top-1 -left-1 w-2.5 h-2.5 border-t-2 border-l-2 border-secondary" />
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 border-t-2 border-r-2 border-secondary" />
              <span className="absolute -bottom-1 -left-1 w-2.5 h-2.5 border-b-2 border-l-2 border-secondary" />
              <span className="absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b-2 border-r-2 border-secondary" />

              <span className="material-symbols-outlined text-[48px] text-on-surface-variant">
                search_off
              </span>
            </div>

            {/* Heading */}
            <h1 className="font-display text-2xl text-on-surface mb-4 flex items-center justify-center gap-3 flex-wrap">
              <span className="text-error text-glow-error">!</span>
              <span>NO STRONG MATCHES FOUND</span>
              <span className="text-error text-glow-error">!</span>
            </h1>

            {/* Subtext */}
            <div className="font-mono text-xs text-on-surface-variant space-y-1.5 mb-8 max-w-md">
              <p>&gt; Nothing in the current catalog matches your idea closely enough.</p>
              <p className="text-error">
                &gt; Status: 404_CONCEPT_NOT_FOUND
                <span className="inline-block w-2 h-4 bg-primary text-primary ml-1.5 terminal-cursor align-middle" />
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-row flex-wrap items-center justify-center gap-4">
              <Link
                to="/build"
                className="font-mono text-xs uppercase px-6 py-3 bg-secondary-container text-white flex items-center gap-2 hover:bg-secondary-container/90 transition-all glow-magenta"
              >
                <span className="material-symbols-outlined text-base">construction</span>
                <span>BUILD THIS IDEA</span>
              </Link>

              <Link
                to="/"
                className="font-mono text-xs uppercase px-6 py-3 border border-primary text-primary flex items-center gap-2 hover:bg-primary/10 transition-all glow-cyan"
              >
                <span className="material-symbols-outlined text-base">tune</span>
                <span>REFINE SEARCH</span>
              </Link>
            </div>
          </div>
        </div>

        {/* Suggestion Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8 w-full">
          <div className="bg-surface-container border border-outline-variant p-4 transition-all duration-200 hover:border-primary cursor-pointer group">
            <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold mb-1">
              <span className="material-symbols-outlined text-base">casino</span>
              <span>&gt; RANDOMIZE</span>
            </div>
            <p className="text-on-surface-variant text-xs font-body">
              Explore chaotic generation vectors.
            </p>
          </div>

          <div className="bg-surface-container border border-outline-variant p-4 transition-all duration-200 hover:border-tertiary cursor-pointer group">
            <div className="flex items-center gap-2 text-tertiary font-mono text-xs font-bold mb-1">
              <span className="material-symbols-outlined text-base">history</span>
              <span>&gt; PREVIOUS_QUERIES</span>
            </div>
            <p className="text-on-surface-variant text-xs font-body">
              Access recent search parameters.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NoMatchesPage;
