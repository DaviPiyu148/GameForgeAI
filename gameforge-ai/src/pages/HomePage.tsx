import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { discoveryService } from '../services/discovery';
import { GameDetailsModal } from '../components/Shared/GameDetailsModal';
import type { DiscoverySearchResult } from '../types';

const INITIAL_VISIBLE_RESULTS = 12;

const HomePage = () => {
  const [promptText, setPromptText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_RESULTS);
  const [isActionLoading, setIsActionLoading] = useState<string | null>(null);
  const [selectedGameForDetails, setSelectedGameForDetails] = useState<DiscoverySearchResult | null>(null);
  const [failedCardImages, setFailedCardImages] = useState<Record<string, boolean>>({});
  const navigate = useNavigate();
  const {
    setPrompt,
    updateBuildParams,
    state,
    setState,
    searchDiscovery,
    clearDiscoveryResults,
    saveDiscovery,
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

  const handleChipClick = (text: string) => {
    setPromptText(text);
    setPrompt(text);
    searchDiscovery(text, navigate);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (promptText.trim()) {
      searchDiscovery(promptText, navigate);
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

  const handleMoreLikeThis = async (gameId: string, gameTitle: string) => {
    try {
      setIsActionLoading(gameId);
      const res = await discoveryService.getSimilarGames(gameId, 24);
      setPromptText(`games like ${gameTitle}`);
      setPrompt(`games like ${gameTitle}`);
      setState((s) => ({
        ...s,
        discoveryResults: res.results || [],
      }));
      window.scrollTo({ top: 400, behavior: 'smooth' });
    } catch (err) {
      console.warn('Failed to fetch similar games:', err);
    } finally {
      setIsActionLoading(null);
    }
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
          <span>DISCOVERY ENGINE 2.0 // HYBRID FAISS + LEXICAL RANKER</span>
        </div>

        {/* Main Heading */}
        <h1 className="font-display text-3xl sm:text-4xl md:text-5xl text-white leading-tight tracking-tight max-w-3xl">
          Describe the game you
          <br className="hidden sm:inline" />{' '}
          <span className="text-secondary text-glow-magenta">wish existed.</span>
        </h1>

        {/* Subtitle Paragraph */}
        <p className="text-on-surface-variant font-body text-base sm:text-lg max-w-2xl text-center leading-relaxed">
          GameForge AI combines dense semantic embeddings with full lexical indexing, intent classification, and IGDB enrichment to discover existing games and synthesize playable prototypes.
        </p>
      </section>

      {/* 2. Terminal Input */}
      <section className="w-full max-w-3xl mx-auto mb-4 stagger-enter stagger-2">
        <form
          onSubmit={handleSubmit}
          className="bg-terminal-bg rounded-lg border border-primary/50 glow-box-cyan focus-within:border-primary-bright focus-within:shadow-[0_0_20px_rgba(76,224,210,0.5)] transition-all overflow-hidden shadow-2xl"
        >
          {/* Header bar */}
          <div className="bg-terminal-header px-4 py-2.5 flex items-center justify-between border-b border-outline-variant/30">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-secondary inline-block"></span>
              <span className="w-3 h-3 rounded-full bg-tertiary inline-block"></span>
              <span className="w-3 h-3 rounded-full bg-primary inline-block"></span>
            </div>
            <span className="font-mono text-xs text-on-surface-variant font-semibold tracking-wide">
              bash - gameforge discovery_engine_2.0
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

      {/* 3. Suggestion Chips (when no results or fresh query) */}
      {!hasResults && !state.isSearching && (
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

          <button
            type="button"
            onClick={() => handleChipClick('Space survival arena')}
            className="border border-primary text-primary font-mono text-xs px-3.5 py-1.5 rounded-full hover:bg-primary/10 hover:shadow-[0_0_10px_rgba(76,224,210,0.2)] transition-all cursor-pointer inline-flex items-center gap-1.5 icon-interactive"
          >
            <span>&gt; Space survival arena</span>
          </button>
        </section>
      )}

      {/* 4. Live Searching State */}
      {state.isSearching && (
        <section className="w-full max-w-5xl mx-auto my-12 bg-terminal-bg border border-primary/40 rounded-lg p-8 text-center glow-box-cyan">
          <div className="flex items-center justify-center gap-3 mb-4">
            <span className="w-3 h-3 rounded-full bg-primary ai-pulse inline-block"></span>
            <span className="font-mono text-primary text-sm uppercase font-bold tracking-widest">
              [DISCOVERY 2.0] RETRIEVING CANDIDATES & RANKING HYBRID SIGNALS...
            </span>
          </div>
          <p className="font-mono text-xs text-on-surface-variant max-w-lg mx-auto">
            Executing hybrid FAISS semantic search + lexical token index, applying Reciprocal Rank Fusion, and calibrating match confidence.
          </p>
        </section>
      )}

      {/* 5. Discovery Results Section (Displayed on Home Page) */}
      {hasResults && !state.isSearching && (
        <section className="w-full max-w-6xl mx-auto my-8 space-y-6 animate-fade-in">
          {/* Header Console */}
          <div className="bg-terminal-bg border border-primary/40 rounded-lg p-4 sm:p-6 glow-box-cyan flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 ai-pulse inline-block"></span>
                <span className="font-mono text-xs text-primary font-bold tracking-widest uppercase">
                  DISCOVERY 2.0 // HYBRID RANKING & ENRICHMENT
                </span>
              </div>
              <h2 className="font-display text-lg sm:text-xl text-white uppercase tracking-wide">
                Matched Games ({state.discoveryResults?.length} Candidates)
              </h2>
              <p className="font-mono text-xs text-on-surface-variant mt-1">
                Concept: &ldquo;{promptText || state.currentPrompt}&rdquo;
              </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
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
                  </div>

                  {/* Top: Score Badge & Title */}
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      {/* Calibrated Match Score Badge */}
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

                      {/* Platforms / Year / Language */}
                      <div className="font-mono text-[10px] text-on-surface-variant text-right flex items-center gap-1 justify-end">
                        <span>{result.game.release_year > 0 ? result.game.release_year : 'Steam'}</span>
                        <span>•</span>
                        <span>{result.game.platforms?.join(', ') || 'PC'}</span>
                        {result.game.description_language && result.game.description_language !== 'en' && (
                          <span
                            title="Localized source description"
                            className="ml-1 px-1.5 py-0.2 rounded text-[9px] font-mono uppercase bg-surface-container border border-outline-variant text-on-surface-variant/80"
                          >
                            {result.game.description_language.toUpperCase()}
                          </span>
                        )}
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

                  {/* Middle: AI Match Insights Box */}
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
                  </div>

                  {/* Bottom: Action Buttons */}
                  <div className="pt-3 border-t border-outline-variant/30 flex items-center gap-2">
                    {/* Save Action */}
                    <button
                      type="button"
                      onClick={() => saveDiscovery(result.game.external_id)}
                      disabled={isSaved}
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

                    {/* More Intel Modal Action */}
                    <button
                      type="button"
                      onClick={() => setSelectedGameForDetails(result)}
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
                      className="flex-1 px-2 py-2 bg-primary text-on-primary font-mono text-[10px] sm:text-[11px] uppercase font-bold rounded btn-interactive glow-cyan flex items-center justify-center gap-1 cursor-pointer"
                      title="Synthesize game prototype inspired by this title"
                    >
                      <span className="material-symbols-outlined text-xs">construction</span>
                      <span>Build</span>
                    </button>
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

      {/* 6. Features Bento Grid (when no search results are active) */}
      {!hasResults && !state.isSearching && (
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
          onMoreLikeThis={handleMoreLikeThis}
          isActionLoading={
            isActionLoading ===
            `build-${selectedGameForDetails.game.external_id || selectedGameForDetails.game.id}`
          }
        />
      )}
    </div>
  );
};

export default HomePage;
