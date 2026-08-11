import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';

const HomePage = () => {
  const [promptText, setPromptText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const navigate = useNavigate();
  const { setPrompt, state } = useAppContext();

  // Sync initial prompt from context if needed, but usually homepage is fresh.
  useEffect(() => {
    if (state.currentPrompt) {
      setPromptText(state.currentPrompt);
    }
  }, [state.currentPrompt]);

  const handleChipClick = (text: string) => {
    setPromptText(text);
    setPrompt(text); // Also update context immediately
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (promptText.trim()) {
      setPrompt(promptText);
      navigate('/discover/no-matches');
    } else {
      navigate('/build');
    }
  };

  const toggleMic = () => {
    setIsListening(!isListening);
    if (!isListening && !promptText.trim()) {
      const text = 'Co-op sci-fi roguelite with deck-building mechanics...';
      setPromptText(text);
      setPrompt(text);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center py-6 px-4">
      {/* 1. Hero Section */}
      <section className="mx-auto flex flex-col items-center text-center max-w-4xl space-y-6 mt-4 mb-10 stagger-enter stagger-1">
        {/* Status Pill */}
        <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-terminal-bg glow-box-cyan text-xs font-mono text-primary font-medium uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-emerald-400 ai-pulse inline-block"></span>
          <span>AI-POWERED GAME DISCOVERY</span>
        </div>

        {/* Main Heading */}
        <h1 className="font-display text-3xl sm:text-4xl md:text-5xl text-white leading-tight tracking-tight max-w-3xl">
          Describe the game you
          <br className="hidden sm:inline" />{' '}
          <span className="text-secondary text-glow-magenta">wish existed.</span>
        </h1>

        {/* Subtitle Paragraph */}
        <p className="text-on-surface-variant font-body text-base sm:text-lg max-w-2xl text-center leading-relaxed">
          GameForge AI transforms your natural language descriptions into custom game concepts, matches existing titles, and synthesizes playable blueprints in real-time.
        </p>
      </section>

      {/* 2. Terminal Input */}
      <section className="w-full max-w-3xl mx-auto mb-4 stagger-enter stagger-2">
        <form onSubmit={handleSubmit} className="bg-terminal-bg rounded-lg border border-primary/50 glow-box-cyan focus-within:border-primary-bright focus-within:shadow-[0_0_20px_rgba(76,224,210,0.5)] transition-all overflow-hidden shadow-2xl">
          {/* Header bar */}
          <div className="bg-terminal-header px-4 py-2.5 flex items-center justify-between border-b border-outline-variant/30">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-secondary inline-block"></span>
              <span className="w-3 h-3 rounded-full bg-tertiary inline-block"></span>
              <span className="w-3 h-3 rounded-full bg-primary inline-block"></span>
            </div>
            <span className="font-mono text-xs text-on-surface-variant font-semibold tracking-wide">
              bash - gameforge
            </span>
            <div className="w-12"></div>
          </div>

          {/* Body */}
          <div className="p-4 sm:p-5 flex items-center gap-3 bg-terminal-bg">
            <span className="text-primary font-mono font-bold text-lg select-none shrink-0">
              ~ $
            </span>

            <div className="flex-1 flex items-center relative min-w-0">
              <input
                type="text"
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="A relaxing 2D co-op survival game with crafting..."
                className="w-full bg-transparent text-on-surface font-mono text-sm sm:text-base outline-none border-none p-0 focus:ring-0 placeholder:text-on-surface-variant/40"
              />
              <span className="w-2 h-4 bg-primary terminal-cursor inline-block shrink-0 ml-1"></span>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={toggleMic}
                title="Toggle Voice Input"
                className={`p-2 transition-colors flex items-center justify-center rounded cursor-pointer icon-interactive ${
                  isListening ? 'text-secondary text-glow-magenta mic-listening' : 'text-on-surface-variant hover:text-primary'
                }`}
              >
                <span className="material-symbols-outlined text-xl">mic</span>
              </button>

              <button
                type="submit"
                className="px-4 py-2 bg-primary text-on-primary font-mono text-xs sm:text-sm font-bold uppercase rounded btn-interactive energy-sweep glow-cyan flex items-center gap-1.5 cursor-pointer"
              >
                <span>Enter</span>
                <span className="material-symbols-outlined text-sm font-bold">keyboard_return</span>
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* 3. Suggestion Chips */}
      <section className="flex flex-wrap items-center justify-center gap-3 w-full max-w-3xl mx-auto mb-16 sm:mb-20 stagger-enter stagger-3">
        <button
          type="button"
          onClick={() => handleChipClick('Cozy farming + exploration')}
          className="border border-secondary text-secondary font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-secondary/10 hover:shadow-[0_0_10px_rgba(255,61,129,0.2)] transition-all cursor-pointer inline-flex items-center gap-1.5 icon-interactive"
        >
          <span>&gt; Cozy farming + exploration</span>
        </button>

        <button
          type="button"
          onClick={() => handleChipClick('Cyberpunk co-op shooter')}
          className="border border-tertiary text-tertiary font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-tertiary/10 hover:shadow-[0_0_10px_rgba(255,194,76,0.2)] transition-all cursor-pointer inline-flex items-center gap-1.5 icon-interactive"
        >
          <span>&gt; Cyberpunk co-op shooter</span>
        </button>
      </section>

      {/* 4. Features Bento Grid */}
      <section className="w-full max-w-5xl mx-auto mt-8 stagger-enter stagger-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="bg-terminal-bg rounded-lg p-6 glow-box-cyan flex flex-col items-start transition-colors hover:border-primary-bright hover:shadow-[0_0_20px_rgba(76,224,210,0.5)] group">
            <div className="w-12 h-12 rounded-lg bg-terminal-header border border-primary/40 flex items-center justify-center mb-5 shrink-0 group-hover:bg-primary/10 transition-colors">
              <span className="material-symbols-outlined text-primary text-2xl">psychology</span>
            </div>
            <h3 className="text-primary text-glow-cyan font-display text-sm md:text-base mb-3 leading-snug uppercase">
              Understand Intent
            </h3>
            <p className="text-on-surface-variant font-body text-sm leading-relaxed">
              Natural language parsing extracts core gameplay loops, thematic vibes, mechanics, and visual styles from prompt inputs.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-terminal-bg rounded-lg p-6 glow-box-magenta flex flex-col items-start transition-colors hover:border-secondary hover:shadow-[0_0_20px_rgba(255,61,129,0.5)] group">
            <div className="w-12 h-12 rounded-lg bg-terminal-header border border-secondary/40 flex items-center justify-center mb-5 shrink-0 group-hover:bg-secondary/10 transition-colors">
              <span className="material-symbols-outlined text-secondary text-2xl">radar</span>
            </div>
            <h3 className="text-secondary text-glow-magenta font-display text-sm md:text-base mb-3 leading-snug uppercase">
              Find Matches
            </h3>
            <p className="text-on-surface-variant font-body text-sm leading-relaxed">
              Deep vector indexing compares your concept against 50,000+ indie and AAA games to identify market gaps and similarity scores.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-terminal-bg rounded-lg p-6 glow-box-amber flex flex-col items-start transition-colors hover:border-tertiary-bright hover:shadow-[0_0_20px_rgba(255,194,76,0.5)] group">
            <div className="w-12 h-12 rounded-lg bg-terminal-header border border-tertiary/40 flex items-center justify-center mb-5 shrink-0 group-hover:bg-tertiary/10 transition-colors">
              <span className="material-symbols-outlined text-tertiary text-2xl">architecture</span>
            </div>
            <h3 className="text-tertiary text-glow-amber font-display text-sm md:text-base mb-3 leading-snug uppercase">
              Build Ideas
            </h3>
            <p className="text-on-surface-variant font-body text-sm leading-relaxed">
              Generates actionable game design documents, target audience profiles, core loop breakdowns, and pitch blueprints instantly.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
