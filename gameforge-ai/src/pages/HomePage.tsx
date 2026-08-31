import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { discoveryService } from '../services/discovery';
import { GameDetailsModal } from '../components/Shared/GameDetailsModal';
import { TuneRecommendationsModal } from '../components/Shared/TuneRecommendationsModal';
import { GameComparisonModal } from '../components/Shared/GameComparisonModal';
import { GameDNAOnboardingModal } from '../components/Shared/GameDNAOnboardingModal';
import type { DiscoverySearchResult } from '../types';

const INITIAL_VISIBLE_RESULTS = 12;

type DiscoveryMode = 'BEST_MATCH' | 'DISCOVER' | 'HIDDEN_GEMS' | 'POPULAR';

const HomePage = () => {
  const [promptText, setPromptText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_RESULTS);
  const [isActionLoading, setIsActionLoading] = useState<string | null>(null);
  const [selectedGameForDetails, setSelectedGameForDetails] = useState<DiscoverySearchResult | null>(null);
  const [failedCardImages, setFailedCardImages] = useState<Record<string, boolean>>({});
  const [activeMode, setActiveMode] = useState<DiscoveryMode>('BEST_MATCH');
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, string>>({});
  const [comparedGameIds, setComparedGameIds] = useState<string[]>([]);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const [isTuneModalOpen, setIsTuneModalOpen] = useState(false);
  const [isOnboardingModalOpen, setIsOnboardingModalOpen] = useState(false);
  const recognitionRef = useRef<any>(null);

  const navigate = useNavigate();
  const {
    setPrompt,
    updateBuildParams,
    state,
    setState,
    searchDiscovery,
    clearDiscoveryResults,
    saveDiscovery,
    pushToast,
  } = useAppContext();

  // Sync initial prompt from context if needed
  useEffect(() => {
    if (state.currentPrompt) {
      setPromptText(state.currentPrompt);
    }
  }, [state.currentPrompt]);

  // Reset visible count when results change
  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE_RESULTS);
  }, [state.discoveryResults?.length]);

  // Clean up speech recognition on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  const handleChipClick = (text: string) => {
    setPromptText(text);
    setPrompt(text);
    searchDiscovery(text, navigate, activeMode);
  };

  const handleModeChange = (mode: DiscoveryMode) => {
    setActiveMode(mode);
    if (promptText.trim()) {
      searchDiscovery(promptText, navigate, mode);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (promptText.trim()) {
      searchDiscovery(promptText, navigate, activeMode);
    } else {
      navigate('/build');
    }
  };

  const toggleMic = () => {
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: any; webkitSpeechRecognition?: any }).SpeechRecognition ||
      (window as unknown as { SpeechRecognition?: any; webkitSpeechRecognition?: any }).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      pushToast({
        variant: 'info',
        title: 'VOICE SEARCH',
        description: "Voice search isn't supported in this browser.",
      });
      return;
    }

    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {
        console.warn('Error stopping speech recognition:', err);
      }
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript.trim()) {
          setPromptText(transcript);
          setPrompt(transcript);
        }
      };

      recognition.onerror = (event: any) => {
        setIsListening(false);
        if (event.error === 'not-allowed') {
          pushToast({
            variant: 'error',
            title: 'MICROPHONE ACCESS',
            description: 'Microphone permission was denied. Please allow microphone access in browser settings.',
          });
        }
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn('Speech recognition start failed:', err);
      setIsListening(false);
    }
  };

  const handleFeedback = async (gameId: string, feedbackType: 'like' | 'dislike' | 'less_like_this') => {
    setFeedbackGiven((prev) => ({ ...prev, [gameId]: feedbackType }));
    try {
      await discoveryService.submitFeedback(gameId, feedbackType);
      if (feedbackType === 'less_like_this') {
        // Add to session context and filter out immediately
        setState((s) => ({
          ...s,
          discoveryResults: (s.discoveryResults || []).filter(
            (r) => r.game.id !== gameId && r.game.external_id !== gameId
          ),
          discoverySession: {
            ...s.discoverySession,
            less_like_this_game_ids: [
              ...(s.discoverySession?.less_like_this_game_ids || []),
              gameId,
            ],
          },
        }));
      }
    } catch (err) {
      console.warn('Failed to submit discovery feedback:', err);
    }
  };

  const handleRefinement = (refinementText: string) => {
    const combinedPrompt = `${promptText} ${refinementText}`.trim();
    setPromptText(combinedPrompt);
    setPrompt(combinedPrompt);
    searchDiscovery(combinedPrompt, navigate, activeMode);
  };

  const handleBuildSimilar = async (result: DiscoverySearchResult) => {
    const gameId = result.game.external_id || result.game.id;
    try {
      setIsActionLoading(`build-${gameId}`);
      const inspiration = await discoveryService.getBuildInspiration(gameId);

      updateBuildParams({
        modules: inspiration.suggested_modules,
        ...(inspiration.suggested_art_density !== undefined ? { artDensity: inspiration.suggested_art_density } : {}),
        ...(inspiration.suggested_physics !== undefined ? { physics: inspiration.suggested_physics } : {}),
      });
      setPrompt(inspiration.recommended_prompt);
      navigate('/build');
    } catch (err) {
      console.warn('Failed to fetch build inspiration, using fallback:', err);
      const promptToUse = result.game.description
        ? `${result.game.title}: ${result.game.description}`
        : result.game.title;
      setPrompt(promptToUse);
      navigate('/build');
    } finally {
      setIsActionLoading(null);
    }
  };

  const hasResults = Boolean(state.discoveryResults && state.discoveryResults.length > 0);
  const displayedResults = (state.discoveryResults || []).slice(0, visibleCount);

  return (
    <div className="flex-1 flex flex-col items-center justify-center py-6 px-4">
      {/* 1. Hero Section */}
      <section className="mx-auto flex flex-col items-center text-center max-w-4xl space-y-6 mt-4 mb-10 stagger-enter stagger-1">
        {/* Status Pill */}
        <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-terminal-bg glow-box-cyan text-xs font-mono text-primary font-medium uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-emerald-400 ai-pulse inline-block"></span>
          <span>DISCOVERY INTELLIGENCE V1 // MULTI-SIGNAL ENGINE</span>
        </div>

        {/* Main Heading */}
        <div className="space-y-2">
          <h1 className="font-display tracking-tight text-3xl sm:text-4xl md:text-5xl lg:text-6xl text-white uppercase glow-text-cyan">
            DISCOVER & REMIX <br className="hidden sm:inline" />
            <span className="text-secondary glow-text-magenta">ANY GAME CONCEPT</span>
          </h1>
          <p className="font-body text-sm sm:text-base md:text-lg text-on-surface-variant max-w-2xl mx-auto leading-relaxed">
            Search 120,000+ PC titles with natural intent, mood, and negative filters — or jumpstart playable browser prototypes.
          </p>
        </div>
      </section>

      {/* 2. Interactive Discovery Search & Mode Selector */}
      <section className="w-full max-w-3xl mx-auto space-y-4 mb-6 stagger-enter stagger-2">
        {/* Mode Selector Tabs */}
        <div className="flex items-center justify-center gap-2 flex-wrap">
          {(
            [
              { id: 'BEST_MATCH', label: 'Best Match', icon: 'verified' },
              { id: 'DISCOVER', label: 'Discover', icon: 'explore' },
              { id: 'HIDDEN_GEMS', label: 'Hidden Gems', icon: 'diamond' },
              { id: 'POPULAR', label: 'Popular', icon: 'local_fire_department' },
            ] as const
          ).map((m) => {
            const isSelected = activeMode === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => handleModeChange(m.id)}
                className={`px-3.5 py-1.5 rounded-full font-mono text-xs uppercase font-bold tracking-wider flex items-center gap-1.5 transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-primary text-on-primary shadow-[0_0_12px_rgba(76,224,210,0.5)]'
                    : 'border border-outline-variant bg-terminal-bg text-on-surface-variant hover:border-primary/50 hover:text-white'
                }`}
              >
                <span className="material-symbols-outlined text-sm">{m.icon}</span>
                <span>{m.label}</span>
              </button>
            );
          })}
        </div>

        {/* Search Input Bar */}
        <form onSubmit={handleSubmit} className="w-full">
          <div className="relative bg-terminal-bg border-2 border-primary/60 rounded-xl p-2 sm:p-3 shadow-2xl glow-box-cyan flex items-center gap-2 sm:gap-3 transition-all focus-within:border-primary focus-within:glow-box-cyan-intense">
            <span className="material-symbols-outlined text-primary text-2xl pl-2 hidden sm:inline">search</span>
            <input
              type="text"
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder="e.g. relaxing farming game without horror, or games like Cyberpunk but less combat..."
              className="flex-1 bg-transparent text-white font-mono text-xs sm:text-sm md:text-base outline-none placeholder:text-on-surface-variant/50 px-2"
            />

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={toggleMic}
                title="Toggle Voice Input"
                aria-label="Toggle voice input"
                className={`p-2 transition-colors flex items-center justify-center rounded cursor-pointer icon-interactive ${
                  isListening ? 'text-secondary text-glow-magenta mic-listening' : 'text-on-surface-variant hover:text-primary'
                }`}
              >
                <span className="material-symbols-outlined text-xl">mic</span>
              </button>

              <button
                type="submit"
                disabled={state.isSearching}
                className="px-4 py-2 bg-primary text-on-primary font-mono text-xs sm:text-sm font-bold uppercase rounded btn-interactive energy-sweep glow-cyan flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {state.isSearching ? (
                  <span>Searching...</span>
                ) : (
                  <>
                    <span>Search</span>
                    <span className="material-symbols-outlined text-sm font-bold">keyboard_return</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* 3. Suggestion & Refinement Chips */}
      {!hasResults && !state.isSearching && (
        <section className="flex flex-wrap items-center justify-center gap-3 w-full max-w-3xl mx-auto mb-16 sm:mb-20 stagger-enter stagger-3">
          <button
            type="button"
            onClick={() => handleChipClick('Cozy farming without horror')}
            className="border border-secondary text-secondary font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-secondary/10 hover:shadow-[0_0_10px_rgba(255,61,129,0.2)] transition-all cursor-pointer inline-flex items-center gap-1.5 icon-interactive"
          >
            <span>&gt; Cozy farming without horror</span>
          </button>

          <button
            type="button"
            onClick={() => handleChipClick('Cyberpunk co-op shooter')}
            className="border border-tertiary text-tertiary font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-tertiary/10 hover:shadow-[0_0_10px_rgba(255,194,76,0.2)] transition-all cursor-pointer inline-flex items-center gap-1.5 icon-interactive"
          >
            <span>&gt; Cyberpunk co-op shooter</span>
          </button>

          <button
            type="button"
            onClick={() => handleChipClick('Space exploration no pvp')}
            className="border border-primary text-primary font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-primary/10 hover:shadow-[0_0_10px_rgba(76,224,210,0.2)] transition-all cursor-pointer inline-flex items-center gap-1.5 icon-interactive"
          >
            <span>&gt; Space exploration no pvp</span>
          </button>

          <button
            type="button"
            onClick={() => setIsOnboardingModalOpen(true)}
            className="bg-primary/20 border border-primary text-primary-bright font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-primary/30 hover:shadow-[0_0_12px_rgba(76,224,210,0.4)] transition-all cursor-pointer inline-flex items-center gap-1.5 font-bold"
          >
            <span className="material-symbols-outlined text-xs">dna</span>
            <span>Build Game DNA</span>
          </button>
        </section>
      )}

      {/* Quick Mood & Discovery Explorer Bar */}
      {!hasResults && !state.isSearching && (
        <section className="w-full max-w-3xl mx-auto mb-12 text-center space-y-3 stagger-enter stagger-3">
          <div className="flex items-center justify-center gap-2 text-xs font-mono text-on-surface-variant uppercase tracking-wider font-bold">
            <span className="material-symbols-outlined text-primary text-sm">bolt</span>
            <span>QUICK MOOD DISCOVERY</span>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {[
              { label: 'Relax & Chill', prompt: 'relaxing cozy simulation no combat' },
              { label: 'High Intensity', prompt: 'fast paced action adrenaline bullet hell' },
              { label: 'Deep Exploration', prompt: 'atmospheric exploration discovery open world' },
              { label: 'Rich Story', prompt: 'narrative rich atmospheric deep lore rpg' },
              { label: 'Tactical Mind', prompt: 'tactical turn-based strategy puzzle thinking' },
              { label: 'Surprise Me 🎲', prompt: 'innovative hidden gem experimental indie' },
            ].map((m) => (
              <button
                key={m.label}
                type="button"
                onClick={() => handleChipClick(m.prompt)}
                className="px-3 py-1 bg-surface-container-highest/40 hover:bg-surface-container-highest border border-outline-variant/50 hover:border-primary/50 text-on-surface hover:text-white font-mono text-xs rounded transition-colors cursor-pointer"
              >
                {m.label}
              </button>
            ))}
          </div>
        </section>
      )}


      {/* 4. Live Searching State */}
      {state.isSearching && (
        <section className="w-full max-w-5xl mx-auto my-12 bg-terminal-bg border border-primary/40 rounded-lg p-8 text-center glow-box-cyan">
          <div className="flex items-center justify-center gap-3 mb-4">
            <span className="w-3 h-3 rounded-full bg-primary ai-pulse inline-block"></span>
            <span className="font-mono text-primary text-sm uppercase font-bold tracking-widest">
              [DISCOVERY INTELLIGENCE] SEARCHING & RANKING RELEVANCE...
            </span>
          </div>
          <p className="font-mono text-xs text-on-surface-variant max-w-lg mx-auto">
            Applying structured intent understanding, negative filters, diversity reranking, and personalized calibration.
          </p>
        </section>
      )}

      {/* 5. Discovery Results Section */}
      {hasResults && !state.isSearching && (
        <section className="w-full max-w-6xl mx-auto my-8 space-y-6 animate-fade-in">
          {/* Header Console */}
          <div className="bg-terminal-bg border border-primary/40 rounded-lg p-4 sm:p-6 glow-box-cyan flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 ai-pulse inline-block"></span>
                <span className="font-mono text-xs text-primary font-bold tracking-widest uppercase">
                  DISCOVERY INTELLIGENCE V1 // {activeMode}
                </span>
                {state.discoveryResponse?.personalized && (
                  <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-400 text-[10px] font-mono">
                    TAILORED FOR YOU
                  </span>
                )}
              </div>
              <h2 className="font-display text-lg sm:text-xl text-white uppercase tracking-wide">
                Matched Games ({state.discoveryResults?.length} Candidates)
              </h2>
              {state.discoveryResponse?.why_these && (
                <p className="font-mono text-xs text-primary/90 mt-1 italic">
                  &gt; {state.discoveryResponse.why_these}
                </p>
              )}
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <button
                type="button"
                onClick={() => setIsTuneModalOpen(true)}
                className="px-3.5 py-2 border border-primary/60 bg-primary/10 hover:bg-primary/20 text-primary font-mono text-xs uppercase font-bold rounded flex items-center gap-1.5 cursor-pointer shadow-[0_0_10px_rgba(76,224,210,0.2)]"
              >
                <span className="material-symbols-outlined text-sm">tune</span>
                <span>Tune</span>
              </button>

              {comparedGameIds.length >= 2 && (
                <button
                  type="button"
                  onClick={() => setIsCompareModalOpen(true)}
                  className="px-3.5 py-2 bg-gradient-to-r from-primary to-primary-bright text-on-primary font-mono text-xs uppercase font-bold rounded flex items-center gap-1.5 cursor-pointer shadow-[0_0_12px_rgba(76,224,210,0.4)] animate-bounce"
                >
                  <span className="material-symbols-outlined text-sm">compare_arrows</span>
                  <span>Compare ({comparedGameIds.length})</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => navigate('/build')}
                className="px-4 py-2 bg-secondary text-on-secondary font-mono text-xs uppercase font-bold rounded btn-interactive energy-sweep glow-magenta flex items-center gap-2 cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">construction</span>
                <span>Build From Scratch</span>
              </button>

              <button
                type="button"
                onClick={clearDiscoveryResults}
                className="px-3 py-2 border border-outline-variant hover:border-primary text-on-surface-variant hover:text-primary font-mono text-xs uppercase rounded transition-colors cursor-pointer"
              >
                Clear Search
              </button>
            </div>
          </div>


          {/* Quick Interactive Refinement Chips */}
          <div className="flex items-center gap-2 flex-wrap pb-2">
            <span className="font-mono text-xs text-on-surface-variant uppercase font-bold">Refine:</span>
            {['More Relaxing', 'Less Combat', 'Free to Play', 'Under ₹500', 'Co-op Only'].map((ref) => (
              <button
                key={ref}
                type="button"
                onClick={() => handleRefinement(ref)}
                className="px-2.5 py-1 rounded border border-outline-variant hover:border-primary bg-terminal-bg text-on-surface-variant hover:text-primary font-mono text-[11px] transition-colors cursor-pointer"
              >
                + {ref}
              </button>
            ))}
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {displayedResults.map((result) => {
              const gameKey = result.game.id || result.game.external_id;
              const matchPct = Math.round(result.score * 100);
              const isSaved = state.savedDiscoveries.some(
                (sd) => sd.steam_app_id === result.game.external_id
              );
              const isStrong = result.score >= 0.85;
              const isGood = result.score >= 0.70 && result.score < 0.85;
              const tierLabel = isStrong ? 'STRONG MATCH' : isGood ? 'GOOD MATCH' : 'POSSIBLE MATCH';
              const userFeedback = feedbackGiven[gameKey];

              const coverUrl =
                result.game.cover_image_url ||
                result.game.hero_image_url ||
                result.game.enrichment?.cover_url ||
                (result.game.source === 'steam' && result.game.external_id
                  ? `https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/${result.game.external_id}/header.jpg`
                  : null);
              const hasImageError = Boolean(failedCardImages[gameKey]);

              return (
                <div
                  key={gameKey}
                  className="bg-terminal-bg rounded-lg border border-outline-variant/60 hover:border-primary transition-all p-5 flex flex-col justify-between shadow-xl group hover:shadow-[0_0_20px_rgba(76,224,210,0.2)] overflow-hidden"
                >
                  {/* Fixed Aspect Ratio Artwork Header */}
                  <div className="relative h-36 -mx-5 -mt-5 mb-4 overflow-hidden rounded-t-lg bg-surface-container shrink-0">
                    {coverUrl && !hasImageError ? (
                      <img
                        src={coverUrl}
                        alt={result.game.display_title || result.game.title}
                        loading="lazy"
                        className="w-full h-full object-cover opacity-85 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300"
                        onError={() =>
                          setFailedCardImages((prev) => ({ ...prev, [gameKey]: true }))
                        }
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-surface-container via-surface to-background flex flex-col items-center justify-center text-on-surface-variant/40 gap-1">
                        <span className="material-symbols-outlined text-3xl">sports_esports</span>
                        <span className="font-mono text-[10px] uppercase tracking-wider">GameForge Intel</span>
                      </div>
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-terminal-bg via-terminal-bg/30 to-transparent"></div>

                    {/* Hidden Gem Badge */}
                    {result.is_hidden_gem && (
                      <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-amber-500/90 text-black font-mono text-[10px] font-bold uppercase tracking-wider shadow">
                        💎 HIDDEN GEM
                      </div>
                    )}
                  </div>

                  {/* Top: Score Badge & Title */}
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      {/* Match Score Badge */}
                      <div
                        className={`px-2.5 py-1 rounded font-mono text-xs font-bold uppercase tracking-wider shrink-0 ${
                          isStrong
                            ? 'bg-emerald-500/10 border border-emerald-400 text-emerald-400 glow-box-cyan'
                            : isGood
                            ? 'bg-secondary/10 border border-secondary text-secondary glow-box-magenta'
                            : 'bg-tertiary/10 border border-tertiary text-tertiary glow-box-amber'
                        }`}
                      >
                        {tierLabel} • {matchPct}%
                      </div>

                      {/* Platforms / Year */}
                      <div className="font-mono text-[10px] text-on-surface-variant text-right flex items-center gap-1 justify-end">
                        <span>{result.game.release_year > 0 ? result.game.release_year : 'Steam'}</span>
                        <span>•</span>
                        <span>{result.game.platforms?.join(', ') || 'PC'}</span>
                      </div>
                    </div>

                    {/* Game Title */}
                    <h3 className="font-display text-base text-white group-hover:text-primary transition-colors line-clamp-2">
                      {result.game.display_title || result.game.title}
                    </h3>

                    {/* Genres & Tags */}
                    <div className="flex flex-wrap gap-1.5">
                      {(result.game.display_genres || result.game.genres)?.slice(0, 3).map((genre) => (
                        <span
                          key={genre}
                          className="px-2 py-0.5 bg-surface-container border border-outline-variant text-[10px] font-mono text-on-surface-variant rounded-sm"
                        >
                          {genre}
                        </span>
                      ))}
                    </div>

                    {/* Description */}
                    <p className="font-body text-xs text-on-surface-variant leading-relaxed line-clamp-3">
                      {result.game.display_description || result.game.description || 'No catalog synopsis available.'}
                    </p>
                  </div>

                  {/* Middle: AI Match Insights & Trade-Offs Box */}
                  <div className="my-4 pt-3 border-t border-outline-variant/30 space-y-2">
                    <div className="flex items-center gap-1.5 text-primary text-[11px] font-mono font-bold uppercase">
                      <span className="material-symbols-outlined text-xs">auto_awesome</span>
                      <span>WHY THIS MATCHES:</span>
                    </div>

                    {/* Highlights Pills */}
                    {result.match_highlights && result.match_highlights.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {result.match_highlights.map((highlight) => (
                          <span
                            key={highlight}
                            className="px-1.5 py-0.5 bg-primary/10 border border-primary/30 text-primary text-[9px] font-mono rounded"
                          >
                            ✓ {highlight}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Deterministic Explanation */}
                    <p className="font-mono text-[11px] text-on-surface-variant/90 italic leading-snug">
                      &gt; {result.explanation}
                    </p>

                    {/* Trade-Offs Pill */}
                    {result.trade_offs && result.trade_offs.length > 0 && (
                      <div className="text-[10px] font-mono text-amber-400/90 flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">info</span>
                        <span>Trade-off: {result.trade_offs[0]}</span>
                      </div>
                    )}

                    {/* Personalization Reason */}
                    {result.personalization_reasons && result.personalization_reasons.length > 0 && (
                      <div className="text-[10px] font-mono text-purple-400 flex items-center gap-1">
                        <span className="material-symbols-outlined text-xs">person</span>
                        <span>{result.personalization_reasons[0]}</span>
                      </div>
                    )}
                  </div>

                  {/* Bottom: Action & Feedback Buttons */}
                  <div className="pt-3 border-t border-outline-variant/30 space-y-2">
                    <div className="flex items-center gap-2">
                      {/* Save Action */}
                      <button
                        type="button"
                        onClick={() => saveDiscovery(result.game.external_id)}
                        disabled={isSaved}
                        aria-label={isSaved ? 'Saved to discoveries' : `Save ${result.game.display_title || result.game.title} to discoveries`}
                        className={`flex-1 px-2 py-2 font-mono text-[10px] sm:text-[11px] uppercase font-bold rounded border transition-colors flex items-center justify-center gap-1 cursor-pointer ${
                          isSaved
                            ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400 cursor-default'
                            : 'border-outline-variant hover:border-primary text-on-surface hover:text-primary hover:bg-primary/5'
                        }`}
                      >
                        <span className="material-symbols-outlined text-xs">
                          {isSaved ? 'bookmark_added' : 'bookmark_add'}
                        </span>
                        <span>{isSaved ? 'Saved' : 'Save'}</span>
                      </button>

                      {/* Details Modal Action */}
                      <button
                        type="button"
                        onClick={() => setSelectedGameForDetails(result)}
                        aria-label={`View rich details and screenshots for ${result.game.display_title || result.game.title}`}
                        className="flex-1 px-2 py-2 border border-secondary/50 text-secondary hover:bg-secondary/10 font-mono text-[10px] sm:text-[11px] uppercase font-bold rounded flex items-center justify-center gap-1 cursor-pointer transition-colors"
                        title="View rich game details, screenshots, and storefront links"
                      >
                        <span className="material-symbols-outlined text-xs">visibility</span>
                        <span>More</span>
                      </button>

                      {/* Build Similar Action */}
                      <button
                        type="button"
                        onClick={() => handleBuildSimilar(result)}
                        disabled={isActionLoading === `build-${result.game.external_id || result.game.id}`}
                        aria-label={`Synthesize game prototype inspired by ${result.game.display_title || result.game.title}`}
                        className="flex-1 px-2 py-2 bg-primary text-on-primary font-mono text-[10px] sm:text-[11px] uppercase font-bold rounded btn-interactive glow-cyan flex items-center justify-center gap-1 cursor-pointer"
                        title="Synthesize game prototype inspired by this title"
                      >
                        <span className="material-symbols-outlined text-xs">construction</span>
                        <span>Build</span>
                      </button>
                    </div>

                    {/* Feedback row: Compare, Like, Dislike, Less Like This */}
                    <div className="flex items-center justify-between text-[10px] font-mono text-on-surface-variant pt-1">
                      <div className="flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          id={`compare-${gameKey}`}
                          checked={comparedGameIds.includes(result.game.external_id || result.game.id)}
                          aria-label={`Compare ${result.game.display_title || result.game.title}`}
                          onChange={() => {
                            const gid = result.game.external_id || result.game.id;
                            setComparedGameIds((prev) =>
                              prev.includes(gid)
                                ? prev.filter((id) => id !== gid)
                                : prev.length < 3
                                ? [...prev, gid]
                                : prev
                            );
                          }}
                          className="w-3 h-3 accent-primary cursor-pointer"
                        />
                        <label
                          htmlFor={`compare-${gameKey}`}
                          className="text-[9px] uppercase tracking-wider text-on-surface-variant/90 cursor-pointer select-none"
                        >
                          Compare
                        </label>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleFeedback(gameKey, 'like')}
                          aria-label={`Like match for ${result.game.display_title || result.game.title}`}
                          className={`hover:text-emerald-400 cursor-pointer flex items-center gap-0.5 ${
                            userFeedback === 'like' ? 'text-emerald-400 font-bold' : ''
                          }`}
                          title="Like this match"
                        >
                          <span className="material-symbols-outlined text-xs">thumb_up</span>
                          <span>Like</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleFeedback(gameKey, 'dislike')}
                          aria-label={`Dislike match for ${result.game.display_title || result.game.title}`}
                          className={`hover:text-secondary cursor-pointer flex items-center gap-0.5 ${
                            userFeedback === 'dislike' ? 'text-secondary font-bold' : ''
                          }`}
                          title="Dislike"
                        >
                          <span className="material-symbols-outlined text-xs">thumb_down</span>
                          <span>Dislike</span>
                        </button>


                        <button
                          type="button"
                          onClick={() => handleFeedback(gameKey, 'less_like_this')}
                          aria-label={`Show fewer matches like ${result.game.display_title || result.game.title}`}
                          className="hover:text-amber-400 cursor-pointer flex items-center gap-0.5"
                          title="Less like this"
                        >
                          <span className="material-symbols-outlined text-xs">block</span>
                          <span>Less</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Show More Button */}
          {state.discoveryResults && state.discoveryResults.length > visibleCount && (
            <div className="flex justify-center pt-4">
              <button
                type="button"
                onClick={() => setVisibleCount((c) => c + INITIAL_VISIBLE_RESULTS)}
                className="px-6 py-3 border-2 border-primary text-primary hover:bg-primary/10 font-mono text-xs uppercase font-bold tracking-wider rounded btn-interactive glow-cyan flex items-center gap-2 cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">expand_more</span>
                <span>Show More Results ({state.discoveryResults.length - visibleCount} remaining)</span>
              </button>
            </div>
          )}
        </section>
      )}

      {/* 6. Features Bento Grid */}
      {!hasResults && !state.isSearching && (
        <section className="w-full max-w-5xl mx-auto mt-8 stagger-enter stagger-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-terminal-bg rounded-lg p-6 glow-box-cyan flex flex-col items-start transition-colors hover:border-primary-bright hover:shadow-[0_0_20px_rgba(76,224,210,0.5)] group">
              <div className="w-12 h-12 rounded-lg bg-terminal-header border border-primary/40 flex items-center justify-center mb-5 shrink-0 group-hover:bg-primary/10 transition-colors">
                <span className="material-symbols-outlined text-primary text-2xl">psychology</span>
              </div>
              <h3 className="text-primary text-glow-cyan font-display text-sm md:text-base mb-3 leading-snug uppercase">
                Understand Intent
              </h3>
              <p className="text-on-surface-variant font-body text-sm leading-relaxed">
                Extracts gameplay loops, moods, time budgets, and hard negative constraints directly from natural language.
              </p>
            </div>

            <div className="bg-terminal-bg rounded-lg p-6 glow-box-magenta flex flex-col items-start transition-colors hover:border-secondary hover:shadow-[0_0_20px_rgba(255,61,129,0.5)] group">
              <div className="w-12 h-12 rounded-lg bg-terminal-header border border-secondary/40 flex items-center justify-center mb-5 shrink-0 group-hover:bg-secondary/10 transition-colors">
                <span className="material-symbols-outlined text-secondary text-2xl">radar</span>
              </div>
              <h3 className="text-secondary text-glow-magenta font-display text-sm md:text-base mb-3 leading-snug uppercase">
                Multi-Signal Ranking
              </h3>
              <p className="text-on-surface-variant font-body text-sm leading-relaxed">
                Blends FAISS vector search, full lexical indexing, community acclaim, and personalized Game DNA affinities.
              </p>
            </div>

            <div className="bg-terminal-bg rounded-lg p-6 glow-box-amber flex flex-col items-start transition-colors hover:border-tertiary-bright hover:shadow-[0_0_20px_rgba(255,194,76,0.5)] group">
              <div className="w-12 h-12 rounded-lg bg-terminal-header border border-tertiary/40 flex items-center justify-center mb-5 shrink-0 group-hover:bg-tertiary/10 transition-colors">
                <span className="material-symbols-outlined text-tertiary text-2xl">architecture</span>
              </div>
              <h3 className="text-tertiary text-glow-amber font-display text-sm md:text-base mb-3 leading-snug uppercase">
                Build & Remix
              </h3>
              <p className="text-on-surface-variant font-body text-sm leading-relaxed">
                Synthesize playable 2D browser games directly from discovered titles using the GameForge studio generator.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* 7. Storefront Intel & Rich Game Details Modal */}
      {selectedGameForDetails && (
        <GameDetailsModal
          result={selectedGameForDetails}
          isSaved={state.savedDiscoveries.some(
            (sd) => sd.steam_app_id === selectedGameForDetails.game.external_id
          )}
          onClose={() => setSelectedGameForDetails(null)}
          onSave={() => saveDiscovery(selectedGameForDetails.game.external_id)}
          onBuildSimilar={(res) => {
            setSelectedGameForDetails(null);
            handleBuildSimilar(res);
          }}
          onMoreLikeThis={async (gameId, gameTitle) => {
            setSelectedGameForDetails(null);
            const res = await discoveryService.getSimilarGames(gameId, 24);
            setPromptText(`games like ${gameTitle}`);
            setPrompt(`games like ${gameTitle}`);
            setState((s) => ({
              ...s,
              discoveryResults: res.results || [],
            }));
            window.scrollTo({ top: 400, behavior: 'smooth' });
          }}
          isActionLoading={
            isActionLoading ===
            `build-${selectedGameForDetails.game.external_id || selectedGameForDetails.game.id}`
          }
        />
      )}

      {/* 8. Tune Recommendations Modal */}

      <TuneRecommendationsModal
        isOpen={isTuneModalOpen}
        onClose={() => setIsTuneModalOpen(false)}
        sessionContext={state.discoverySession || {}}
        onApply={(newContext) => {
          setState((s) => ({ ...s, discoverySession: newContext }));
          if (promptText.trim()) {
            searchDiscovery(promptText, navigate, activeMode, newContext);
          }
        }}
        onReset={() => {
          setState((s) => ({ ...s, discoverySession: {} }));
          if (promptText.trim()) {
            searchDiscovery(promptText, navigate, activeMode, {});
          }
        }}
      />

      {/* 9. Side-by-Side Game Comparison Modal */}
      <GameComparisonModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        selectedGameIds={comparedGameIds}
        onRemoveGame={(id) => {
          setComparedGameIds((prev) => prev.filter((gid) => gid !== id));
        }}
      />

      {/* 10. Cold-Start Game DNA Onboarding Modal */}
      <GameDNAOnboardingModal
        isOpen={isOnboardingModalOpen}
        onClose={() => setIsOnboardingModalOpen(false)}
        onCompleted={() => {
          if (promptText.trim()) {
            searchDiscovery(promptText, navigate, activeMode);
          }
        }}
      />
    </div>

  );
};

export default HomePage;
