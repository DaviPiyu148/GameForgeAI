import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { DiscoverySearchResult, StorefrontItem } from '../../types';
import { useModalDialog } from '../../hooks/useModalDialog';

interface GameDetailsModalProps {
  result: DiscoverySearchResult;
  isSaved: boolean;
  onClose: () => void;
  onSave: () => void;
  onBuildSimilar: (result: DiscoverySearchResult) => void;
  onMoreLikeThis?: (gameId: string, title: string) => void;
  isActionLoading?: boolean;
}

export const GameDetailsModal: React.FC<GameDetailsModalProps> = ({
  result,
  isSaved,
  onClose,
  onSave,
  onBuildSimilar,
  onMoreLikeThis,
  isActionLoading = false,
}) => {
  const [activeScreenshotIndex, setActiveScreenshotIndex] = useState(0);
  const [heroImageError, setHeroImageError] = useState(false);
  const [screenshotErrors, setScreenshotErrors] = useState<Record<number, boolean>>({});
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const { isClosing, handleClose, handleBackdropClick, dialogRef } = useModalDialog({
    isOpen: true,
    onClose,
    initialFocusRef: closeBtnRef,
    closeDelayMs: 200,
  });

  // Reset internal state whenever the selected game changes
  useEffect(() => {
    setActiveScreenshotIndex(0);
    setHeroImageError(false);
    setScreenshotErrors({});
  }, [result.game.id, result.game.external_id]);

  const game = result.game;
  const matchPct = Math.round(result.score * 100);
  const isStrong = result.score >= 0.85;
  const isGood = result.score >= 0.70 && result.score < 0.85;
  const tierLabel = isStrong ? 'STRONG MATCH' : isGood ? 'GOOD MATCH' : 'POSSIBLE MATCH';

  // Hero artwork resolution priority: Hero/Capsule -> Cover -> IGDB Cover
  const heroArtUrl =
    game.hero_image_url ||
    game.cover_image_url ||
    game.enrichment?.cover_url ||
    (game.source === 'steam' && game.external_id
      ? `https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/${game.external_id}/capsule_616x353.jpg`
      : null);

  // Valid screenshots filtered against error states
  const validScreenshots = (game.screenshots || []).filter(
    (url, idx) => Boolean(url) && !screenshotErrors[idx]
  );

  // Storefronts: use structured storefronts or fallback to Steam if external_id exists
  const rawStorefronts: StorefrontItem[] =
    game.storefronts && game.storefronts.length > 0
      ? game.storefronts
      : game.source === 'steam' && game.external_id
      ? [
          {
            provider: 'steam',
            name: 'Steam',
            url: `https://store.steampowered.com/app/${game.external_id}/`,
            platform: 'PC',
          },
        ]
      : [];

  // Filter storefronts to only safe http/https URLs
  const verifiedStorefronts = rawStorefronts.filter((s) => {
    if (!s.url) return false;
    const lower = s.url.toLowerCase().trim();
    return (
      (lower.startsWith('http://') || lower.startsWith('https://')) &&
      !lower.includes('javascript:') &&
      !lower.includes('data:')
    );
  });

  const getProviderIcon = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'steam':
        return 'sports_esports';
      case 'gog':
        return 'download';
      case 'epic':
        return 'shopping_bag';
      case 'playstation':
        return 'gamepad';
      case 'xbox':
        return 'videogame_asset';
      case 'nintendo':
        return 'sports_esports';
      case 'itch':
        return 'storefront';
      default:
        return 'store';
    }
  };

  return createPortal(
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-background/90 backdrop-blur-md ${
        isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
      }`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label={`Details for ${game.display_title || game.title}`}
    >
      <div
        ref={dialogRef}
        className={`w-full max-w-3xl max-h-[92vh] overflow-y-auto bg-surface border border-primary/50 rounded-lg flex flex-col shadow-[0_0_40px_rgba(76,224,210,0.2)] glow-cyan ${
          isClosing ? 'modal-exit' : 'modal-enter'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Top Header Bar */}
        <div className="bg-terminal-header border-b border-primary/30 px-4 py-2.5 flex justify-between items-center sticky top-0 z-20 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-primary">
            <span className="material-symbols-outlined text-base">travel_explore</span>
            <span className="font-mono text-xs tracking-widest font-bold uppercase">
              STOREFRONT_INTEL // {game.external_id || game.id}
            </span>
          </div>
          <button
            ref={closeBtnRef}
            onClick={handleClose}
            className="text-on-surface-variant icon-interactive hover:text-primary transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-primary rounded cursor-pointer"
            aria-label="Close game details"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 bg-terminal-bg flex flex-col">
          {/* 1. Hero Artwork Section */}
          <div className="relative w-full h-48 sm:h-64 md:h-72 bg-surface-container overflow-hidden shrink-0">
            {heroArtUrl && !heroImageError ? (
              <img
                src={heroArtUrl}
                alt={game.display_title || game.title}
                fetchPriority="high"
                loading="eager"
                decoding="async"
                className="w-full h-full object-cover object-center transition-all duration-500"
                onError={() => setHeroImageError(true)}
              />
            ) : (
              <div className="w-full h-full bg-gradient-to-br from-surface-container via-surface to-background flex flex-col items-center justify-center text-on-surface-variant/40 gap-2">
                <span className="material-symbols-outlined text-5xl">sports_esports</span>
                <span className="font-mono text-xs uppercase tracking-wider">GameForge Intel Archive</span>
              </div>
            )}

            {/* Gradient Scrim */}
            <div className="absolute inset-0 bg-gradient-to-t from-terminal-bg via-terminal-bg/60 to-transparent"></div>

            {/* Match Tier Badge Top Right */}
            <div className="absolute top-4 right-4 z-10">
              <div
                className={`px-3 py-1.5 rounded font-mono text-xs font-bold uppercase tracking-wider shadow-lg ${
                  isStrong
                    ? 'bg-emerald-950/80 border border-emerald-400 text-emerald-400 glow-box-cyan'
                    : isGood
                    ? 'bg-purple-950/80 border border-secondary text-secondary glow-box-magenta'
                    : 'bg-amber-950/80 border border-tertiary text-tertiary glow-box-amber'
                }`}
              >
                {tierLabel} • {matchPct}% MATCH
              </div>
            </div>

            {/* Hero Text Bottom Overlay */}
            <div className="absolute bottom-4 left-4 right-4 z-10 space-y-1">
              <h1 className="font-display text-xl sm:text-2xl md:text-3xl text-white font-bold tracking-tight drop-shadow-md">
                {game.display_title || game.title}
              </h1>
              <div className="flex items-center gap-2 flex-wrap font-mono text-xs text-on-surface-variant">
                {game.release_year > 0 && (
                  <span className="text-primary font-bold">{game.release_year}</span>
                )}
                {game.release_year > 0 && <span>•</span>}
                <span>{game.platforms?.join(', ') || 'PC'}</span>
                {game.is_free && (
                  <>
                    <span>•</span>
                    <span className="px-1.5 py-0.2 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded text-[10px] uppercase font-bold">
                      Free To Play
                    </span>
                  </>
                )}
                {game.positive_percent !== undefined && game.positive_percent > 0 && (
                  <>
                    <span>•</span>
                    <span className="text-emerald-400">
                      {Math.round(game.positive_percent)}% Positive
                      {game.total_reviews ? ` (${game.total_reviews.toLocaleString()} reviews)` : ''}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* 2. Main Content Grid */}
          <div className="p-4 sm:p-6 space-y-6">
            {/* Genre & Tag Chips */}
            <div className="flex flex-wrap gap-1.5">
              {(game.display_genres || game.genres || []).map((genre) => (
                <span
                  key={genre}
                  className="px-2.5 py-1 bg-surface-container border border-outline-variant text-xs font-mono text-on-surface rounded-sm"
                >
                  {genre}
                </span>
              ))}
              {(game.display_tags || game.tags || []).slice(0, 6).map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-0.5 bg-surface-container-low border border-outline-variant/40 text-[11px] font-mono text-on-surface-variant rounded-sm"
                >
                  #{tag}
                </span>
              ))}
            </div>

            {/* Game Description */}
            <div className="space-y-2">
              <h2 className="font-mono text-xs text-secondary uppercase tracking-widest font-bold flex items-center gap-1.5">
                <span className="material-symbols-outlined text-sm">subject</span>
                <span>SYNOPSIS & INTEL</span>
              </h2>
              <div className="bg-surface-container-low border border-outline-variant/50 p-4 rounded text-sm text-on-surface/90 leading-relaxed font-body whitespace-pre-line">
                {game.display_description || game.description || 'No catalog synopsis available for this title.'}
              </div>
              {(game.developer || game.publisher) && (
                <div className="flex items-center gap-4 font-mono text-xs text-on-surface-variant pt-1">
                  {game.developer && (
                    <span>
                      DEV: <strong className="text-on-surface">{game.developer}</strong>
                    </span>
                  )}
                  {game.publisher && (
                    <span>
                      PUB: <strong className="text-on-surface">{game.publisher}</strong>
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* 3. Why This Matches Section */}
            <div className="bg-surface-container/60 border border-primary/30 p-4 rounded-lg space-y-3 glow-box-cyan">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2 text-primary font-mono text-xs uppercase font-bold">
                  <span className="material-symbols-outlined text-base">auto_awesome</span>
                  <span>WHY THIS MATCHES YOUR QUERY</span>
                </div>
                <span className="font-mono text-xs text-primary font-bold">
                  {matchPct}% CALIBRATED RELEVANCE
                </span>
              </div>

              {/* Progress Meter */}
              <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden border border-outline-variant/40">
                <div
                  className="h-full bg-gradient-to-r from-primary via-secondary to-emerald-400 transition-all duration-500 rounded-full"
                  style={{ width: `${Math.min(Math.max(matchPct, 5), 100)}%` }}
                ></div>
              </div>

              {/* Matched Highlights */}
              {result.match_highlights && result.match_highlights.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {result.match_highlights.map((highlight) => (
                    <span
                      key={highlight}
                      className="px-2 py-0.5 bg-primary/10 border border-primary/40 text-primary text-[10px] font-mono rounded font-bold"
                    >
                      ✓ {highlight}
                    </span>
                  ))}
                </div>
              )}

              {/* Match Explanation */}
              <p className="font-mono text-xs text-on-surface-variant/95 italic leading-relaxed pt-1">
                &gt; {result.explanation || 'Recommended based on your search concept and thematic profile.'}
              </p>
            </div>

            {/* 4. Screenshot Gallery (Rendered only when real screenshots exist) */}
            {validScreenshots.length > 0 && (
              <div className="space-y-3">
                <h2 className="font-mono text-xs text-secondary uppercase tracking-widest font-bold flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">photo_library</span>
                  <span>SCREENSHOT ARCHIVE ({validScreenshots.length})</span>
                </h2>

                {/* Main Preview */}
                <div className="relative w-full h-52 sm:h-64 bg-surface-container rounded-lg overflow-hidden border border-outline-variant/60">
                  <img
                    src={validScreenshots[activeScreenshotIndex] || validScreenshots[0]}
                    alt={`${game.title} screenshot ${activeScreenshotIndex + 1}`}
                    className="w-full h-full object-cover object-center transition-all duration-300"
                    onError={() =>
                      setScreenshotErrors((prev) => ({ ...prev, [activeScreenshotIndex]: true }))
                    }
                  />
                  <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-1 rounded text-[10px] font-mono text-white">
                    {activeScreenshotIndex + 1} / {validScreenshots.length}
                  </div>
                </div>

                {/* Thumbnails Row */}
                {validScreenshots.length > 1 && (
                  <div className="flex items-center gap-2 overflow-x-auto pb-1">
                    {validScreenshots.map((url, idx) => (
                      <button
                        type="button"
                        key={url}
                        aria-label={`View screenshot ${idx + 1} of ${validScreenshots.length}`}
                        aria-current={idx === activeScreenshotIndex ? 'true' : undefined}
                        onClick={() => setActiveScreenshotIndex(idx)}
                        className={`relative w-20 h-14 shrink-0 rounded overflow-hidden border transition-all cursor-pointer ${
                          idx === activeScreenshotIndex
                            ? 'border-primary shadow-[0_0_10px_rgba(76,224,210,0.5)] scale-105'
                            : 'border-outline-variant/60 opacity-60 hover:opacity-100'
                        }`}
                      >
                        <img
                          src={url}
                          alt=""
                          aria-hidden="true"
                          className="w-full h-full object-cover"
                          onError={() =>
                            setScreenshotErrors((prev) => ({ ...prev, [idx]: true }))
                          }
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 5. Verified Storefronts Section */}
            {verifiedStorefronts.length > 0 && (
              <div className="space-y-3 pt-2">
                <h2 className="font-mono text-xs text-secondary uppercase tracking-widest font-bold flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">storefront</span>
                  <span>AVAILABLE ON STOREFRONTS</span>
                </h2>
                <div className="flex flex-wrap gap-2.5">
                  {verifiedStorefronts.map((store) => (
                    <a
                      key={store.url}
                      href={store.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-surface-container border border-outline-variant hover:border-primary text-on-surface hover:text-primary font-mono text-xs rounded transition-all flex items-center gap-2 group hover:bg-primary/5 cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-sm text-primary">
                        {getProviderIcon(store.provider)}
                      </span>
                      <span className="font-bold">{store.name}</span>
                      <span className="text-[10px] text-on-surface-variant group-hover:text-primary">
                        ({store.platform || 'PC'})
                      </span>
                      <span className="material-symbols-outlined text-xs text-on-surface-variant group-hover:text-primary ml-1">
                        open_in_new
                      </span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 6. Footer Action Bar */}
          <div className="bg-terminal-header border-t border-primary/30 p-4 flex items-center justify-between gap-3 sticky bottom-0 z-20 backdrop-blur-sm flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              {/* Save / Bookmark Button */}
              <button
                type="button"
                onClick={onSave}
                disabled={isSaved}
                className={`px-4 py-2.5 font-mono text-xs uppercase font-bold rounded border transition-colors flex items-center gap-2 cursor-pointer ${
                  isSaved
                    ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400 cursor-default'
                    : 'border-outline-variant hover:border-primary text-on-surface hover:text-primary hover:bg-primary/5'
                }`}
              >
                <span className="material-symbols-outlined text-sm">
                  {isSaved ? 'bookmark_added' : 'bookmark_add'}
                </span>
                <span>{isSaved ? 'Saved in Collection' : 'Save Game'}</span>
              </button>

              {/* Discover More Like This Action */}
              {onMoreLikeThis && (
                <button
                  type="button"
                  onClick={() => {
                    handleClose();
                    onMoreLikeThis(game.external_id || game.id, game.title);
                  }}
                  className="px-3.5 py-2.5 border border-secondary/50 text-secondary hover:bg-secondary/10 font-mono text-xs uppercase font-bold rounded flex items-center gap-1.5 cursor-pointer transition-colors"
                  title="Discover games similar to this title"
                >
                  <span className="material-symbols-outlined text-sm">scatter_plot</span>
                  <span>Find Similar</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
              {/* Close Button */}
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2.5 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded transition-colors cursor-pointer"
              >
                Close
              </button>

              {/* Build Similar Primary Button */}
              <button
                type="button"
                onClick={() => onBuildSimilar(result)}
                disabled={isActionLoading}
                className="px-5 py-2.5 bg-primary text-on-primary font-mono text-xs uppercase font-bold rounded btn-interactive energy-sweep glow-cyan flex items-center gap-2 cursor-pointer shadow-lg"
              >
                <span className="material-symbols-outlined text-sm">construction</span>
                <span>{isActionLoading ? 'Preparing Build...' : 'Build Similar'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
