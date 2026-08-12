import { Link, useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';

const MOCK_PROMPTS = [
  "A neon-drenched cyberpunk racing game with zero gravity mechanics.",
  "Cozy farming simulator but you are a mech pilot defending the crops at night.",
  "Turn-based psychological horror set in a 1920s submarine.",
  "Fast-paced roguelike where you fight using only a deck of cursed tarot cards.",
  "An MMORPG where players manage a dynamic galactic economy and trade rare resources."
];

const NoMatchesPage = () => {
  const { state, setPrompt } = useAppContext();
  const navigate = useNavigate();

  const handleRandomize = () => {
    const randomPrompt = MOCK_PROMPTS[Math.floor(Math.random() * MOCK_PROMPTS.length)];
    setPrompt(randomPrompt);
    navigate('/build');
  };

  const handlePreviousQueries = () => {
    navigate('/dashboard');
  };

  const handleBuildMatch = (matchTitle: string) => {
    setPrompt(`${state.currentPrompt || matchTitle}`);
    navigate('/build');
  };

  const hasMatches = state.recommendations && state.recommendations.length > 0;

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
          {hasMatches ? (
            <div className="bg-terminal-bg border border-outline-variant p-6 flex flex-col rounded-b-md relative overflow-hidden stagger-enter stagger-1">
              <div className="absolute inset-0 scanline-effect opacity-20 pointer-events-none"></div>
              
              {/* Header */}
              <div className="flex items-center justify-between mb-6 pb-3 border-b border-outline-variant relative z-10">
                <div>
                  <h1 className="font-display text-xl text-primary flex items-center gap-2">
                    <span className="material-symbols-outlined text-xl">radar</span>
                    RECOMMENDED MATCHES
                  </h1>
                  <p className="font-mono text-xs text-on-surface-variant mt-1">
                    &gt; Found {state.recommendations.length} title(s) matching: "{state.currentPrompt}"
                  </p>
                </div>
                <div className="px-2.5 py-1 bg-primary/10 border border-primary/40 text-primary font-mono text-[10px] uppercase">
                  MATCH_FOUND
                </div>
              </div>

              {/* Match Cards List */}
              <div className="space-y-4 mb-6 relative z-10">
                {state.recommendations.map(match => (
                  <div 
                    key={match.id}
                    className="bg-surface border border-outline-variant hover:border-primary p-4 rounded-sm transition-all relative group"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-display text-base text-white group-hover:text-primary transition-colors">
                        {match.title}
                      </h3>
                      <div className="flex items-center gap-1 font-mono text-xs text-primary bg-primary/10 px-2 py-0.5 border border-primary/30">
                        <span className="material-symbols-outlined text-[14px]">radar</span>
                        {match.score}% MATCH
                      </div>
                    </div>

                    <p className="font-body text-xs text-on-surface-variant mb-3 leading-relaxed">
                      {match.description}
                    </p>

                    {/* Reasons Pills */}
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {match.reasons.map((reason, idx) => (
                        <span 
                          key={idx}
                          className="font-mono text-[10px] px-2 py-0.5 bg-terminal-header border border-secondary/40 text-secondary rounded-full"
                        >
                          &gt; {reason}
                        </span>
                      ))}
                    </div>

                    <button
                      onClick={() => handleBuildMatch(match.title)}
                      className="font-mono text-xs text-primary hover:text-primary-bright flex items-center gap-1.5 cursor-pointer uppercase font-bold"
                    >
                      <span>Build Prototype Based On This</span>
                      <span className="material-symbols-outlined text-sm">arrow_forward</span>
                    </button>
                  </div>
                ))}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-row flex-wrap items-center justify-center gap-4 relative z-10 border-t border-outline-variant pt-4">
                <Link
                  to="/build"
                  className="font-mono text-xs uppercase px-6 py-3 bg-secondary-container text-white flex items-center gap-2 hover:bg-secondary-container/90 btn-interactive energy-sweep glow-magenta"
                >
                  <span className="material-symbols-outlined text-base">construction</span>
                  <span>BUILD CUSTOM IDEA</span>
                </Link>

                <Link
                  to="/"
                  className="font-mono text-xs uppercase px-6 py-3 border border-primary text-primary flex items-center gap-2 hover:bg-primary/10 btn-interactive glow-cyan"
                >
                  <span className="material-symbols-outlined text-base">tune</span>
                  <span>REFINE SEARCH</span>
                </Link>
              </div>
            </div>
          ) : (
            <div className="bg-terminal-bg border border-outline-variant p-8 flex flex-col items-center text-center rounded-b-md relative overflow-hidden stagger-enter stagger-1">
              <div className="absolute inset-0 scanline-effect opacity-20 pointer-events-none"></div>
              {/* Large Icon Box */}
              <div className="relative w-24 h-24 border-2 border-outline-variant flex items-center justify-center bg-surface/50 mb-6 z-10">
                {/* Corner markers */}
                <span className="absolute -top-1 -left-1 w-2.5 h-2.5 border-t-2 border-l-2 border-secondary" />
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 border-t-2 border-r-2 border-secondary" />
                <span className="absolute -bottom-1 -left-1 w-2.5 h-2.5 border-b-2 border-l-2 border-secondary" />
                <span className="absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b-2 border-r-2 border-secondary" />

                <span className="material-symbols-outlined text-[48px] text-on-surface-variant animate-[pulse_0.5s_ease-out_1]">
                  search_off
                </span>
              </div>

              {/* Heading */}
              <h1 className="font-display text-2xl text-on-surface mb-4 flex items-center justify-center gap-3 flex-wrap relative z-10">
                <span className="text-error text-glow-error">!</span>
                <span>NO STRONG MATCHES FOUND</span>
                <span className="text-error text-glow-error">!</span>
              </h1>

              {/* Subtext */}
              <div className="font-mono text-xs text-on-surface-variant space-y-1.5 mb-8 max-w-md relative z-10">
                <p>&gt; Nothing in the current catalog matches your idea closely enough.</p>
                <p className="text-error">
                  &gt; Status: 404_CONCEPT_NOT_FOUND
                  <span className="inline-block w-2 h-4 bg-primary text-primary ml-1.5 terminal-cursor align-middle" />
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-row flex-wrap items-center justify-center gap-4 relative z-10">
                <Link
                  to="/build"
                  className="font-mono text-xs uppercase px-6 py-3 bg-secondary-container text-white flex items-center gap-2 hover:bg-secondary-container/90 btn-interactive energy-sweep glow-magenta"
                >
                  <span className="material-symbols-outlined text-base">construction</span>
                  <span>BUILD THIS IDEA</span>
                </Link>

                <Link
                  to="/"
                  className="font-mono text-xs uppercase px-6 py-3 border border-primary text-primary flex items-center gap-2 hover:bg-primary/10 btn-interactive glow-cyan"
                >
                  <span className="material-symbols-outlined text-base">tune</span>
                  <span>REFINE SEARCH</span>
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Suggestion Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8 w-full stagger-enter stagger-2">
          <div 
            onClick={handleRandomize}
            className="bg-surface-container border border-outline-variant p-4 transition-all duration-200 hover:border-primary hover:shadow-[0_0_15px_rgba(76,224,210,0.2)] cursor-pointer group btn-interactive"
          >
            <div className="flex items-center gap-2 text-primary font-mono text-xs font-bold mb-1">
              <span className="material-symbols-outlined text-base">casino</span>
              <span>&gt; RANDOMIZE</span>
            </div>
            <p className="text-on-surface-variant text-xs font-body group-hover:text-on-surface transition-colors">
              Explore chaotic generation vectors.
            </p>
          </div>

          <div 
            onClick={handlePreviousQueries}
            className="bg-surface-container border border-outline-variant p-4 transition-all duration-200 hover:border-tertiary hover:shadow-[0_0_15px_rgba(255,194,76,0.2)] cursor-pointer group btn-interactive"
          >
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
