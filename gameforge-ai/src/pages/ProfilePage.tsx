import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';
import type { GameProject } from '../types';

export default function ProfilePage() {
  const { state, setPrompt, updateBuildParams, openAuthModal, logout, removeSavedDiscovery, updateGameProject } = useAppContext();
  const navigate = useNavigate();
  const [selectedPlayProject, setSelectedPlayProject] = useState<GameProject | null>(null);
  const [showLikedGamesModal, setShowLikedGamesModal] = useState(false);
  const [isClosingModal, setIsClosingModal] = useState(false);
  const [displayGames, setDisplayGames] = useState(0);

  const handleCloseModal = () => {
    setIsClosingModal(true);
    setTimeout(() => {
      setShowLikedGamesModal(false);
      setIsClosingModal(false);
    }, 250);
  };

  useEffect(() => {
    const endGames = state.myGames.length;
    const duration = 1000;
    const startTime = performance.now();
    let rafId: number | null = null;
    let cancelled = false;

    const updateCounter = (currentTime: number) => {
      if (cancelled) return;
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOutQuad = 1 - (1 - progress) * (1 - progress);

      setDisplayGames(Math.floor(endGames * easeOutQuad));

      if (progress < 1) {
        rafId = requestAnimationFrame(updateCounter);
      } else {
        setDisplayGames(endGames);
      }
    };

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mediaQuery.matches) {
      setDisplayGames(endGames);
    } else {
      rafId = requestAnimationFrame(updateCounter);
    }

    // Cleanup prevents setState-after-unmount and stops a stale loop from a prior
    // dependency change from still running (and racing) after this effect re-fires.
    return () => {
      cancelled = true;
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [state.myGames.length]);

  const handleContinueEdit = (desc: string) => {
    setPrompt(desc);
    // Must match BuilderPage.tsx's actual <option>/checkbox values — 'Phaser' and
    // 'Advanced NPC AI' matched none of the current Prototype Profile options or Logic
    // Module checkboxes, so the Builder page appeared to reset the selection silently.
    updateBuildParams({
      engine: 'Top-Down Action',
      artDensity: 70,
      physics: 60,
      modules: ['Enhanced NPC Behavior'],
    });
    navigate('/build');
  };

  const username = state.user?.username || 'Guest Architect';
  const email = state.user?.email || 'Unauthenticated Session';
  const level = state.user?.level || 1;

  return (
    <div className="w-full max-w-6xl mx-auto p-4 md:p-6 lg:p-8 space-y-6 animate-fade-in font-body text-on-surface pb-24">
      {/* Profile Header Console */}
      <div className="relative arcade-border bg-surface-container-low p-6 arcade-panel">
        <div className="absolute top-0 left-0 right-0 h-1 bg-primary/30"></div>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative z-10">
          {/* Left: Avatar and Info */}
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 rounded-sm border-4 border-primary bg-surface-container-high flex items-center justify-center shrink-0 glow-box-cyan">
              <span className="material-symbols-outlined text-primary text-[48px]">person</span>
            </div>
            <div className="space-y-2">
              <h1 className="font-display text-xl md:text-2xl text-primary uppercase text-glow-cyan tracking-wider">
                {username}
              </h1>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2 text-tertiary text-sm md:text-base bg-tertiary/10 px-3 py-1.5 rounded-sm border border-tertiary/20 w-fit">
                  <span className="material-symbols-outlined text-[18px]">star</span>
                  <span>Level {level} Architect</span>
                </div>
                <span className="font-mono text-xs text-on-surface-variant">{email}</span>
              </div>
            </div>
          </div>

          {/* Right: Stat boxes & Auth Action */}
          <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
            <div className="bg-surface-container-highest p-4 border border-outline-variant flex-1 md:flex-none min-w-[140px] text-center rounded-sm">
              <div className="text-sm text-on-surface-variant uppercase tracking-wider mb-1">Saved Items</div>
              <div className="font-display text-primary">{state.savedDiscoveries.length}</div>
            </div>
            <div className="bg-surface-container-highest p-4 border border-outline-variant flex-1 md:flex-none min-w-[140px] text-center rounded-sm">
              <div className="text-sm text-on-surface-variant uppercase tracking-wider mb-1">Games Built</div>
              <div className="font-display text-secondary">{displayGames}</div>
            </div>

            {state.authStatus === 'AUTHENTICATED' ? (
              <button
                onClick={logout}
                className="px-4 py-3 border border-error/50 text-error hover:bg-error/10 font-mono text-xs uppercase flex items-center gap-1.5 transition-colors cursor-pointer rounded-sm"
                title="Log out of GameForge AI"
              >
                <span className="material-symbols-outlined text-sm">logout</span>
                <span>Sign Out</span>
              </button>
            ) : (
              <button
                onClick={() => openAuthModal('login')}
                className="px-6 py-3 bg-primary text-on-primary font-mono text-xs uppercase flex items-center gap-1.5 glow-cyan btn-interactive cursor-pointer rounded-sm"
              >
                <span className="material-symbols-outlined text-sm">login</span>
                <span>Sign In / Register</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Grid: Left sidebar and Right details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (col-span-1) */}
        <div className="space-y-6">
          {/* Liked Games Section */}
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel stagger-enter stagger-2">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary">favorite</span>
                <h2 className="font-display text-lg uppercase tracking-wide">Saved Discoveries</h2>
              </div>
              <span className="font-mono text-xs text-on-surface-variant">{state.savedDiscoveries.length} saved</span>
            </div>

            {state.authStatus !== 'AUTHENTICATED' ? (
              <div className="p-4 border border-outline-variant bg-surface-container text-center space-y-3 font-mono text-xs text-on-surface-variant">
                <p>Log in to view and manage your saved discoveries.</p>
                <button
                  onClick={() => openAuthModal('login', 'Log in to access your saved discoveries.')}
                  className="px-4 py-2 bg-secondary-container text-white font-mono text-xs uppercase rounded-sm btn-interactive glow-magenta cursor-pointer"
                >
                  Sign In
                </button>
              </div>
            ) : state.savedDiscoveries.length === 0 ? (
              <div className="p-4 border border-outline-variant bg-surface-container text-center font-mono text-xs text-on-surface-variant">
                No saved discoveries yet. Search games on the Discover page to save them!
              </div>
            ) : (
              <div className="space-y-3">
                {state.savedDiscoveries.slice(0, 4).map((sd) => (
                  <div
                    key={sd.id}
                    className="flex items-center justify-between gap-3 p-3 bg-surface-container-highest/50 border border-outline-variant/50 rounded-sm hover:bg-surface-container-highest hover:border-secondary/30 transition-colors group"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-10 h-10 bg-secondary-container border border-secondary/40 rounded flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-secondary text-lg">sports_esports</span>
                      </div>
                      <div className="overflow-hidden">
                        <h3 className="font-semibold text-on-surface text-xs group-hover:text-primary transition-colors truncate" title={sd.title}>
                          {sd.title}
                        </h3>
                        <p className="text-[10px] text-on-surface-variant truncate">
                          {sd.genres.slice(0, 2).join(', ') || 'Game'}
                        </p>
                      </div>
                    </div>

                    <button
                      onClick={() => removeSavedDiscovery(sd.id)}
                      className="p-1 text-on-surface-variant hover:text-error transition-colors cursor-pointer shrink-0"
                      title="Remove from saved"
                    >
                      <span className="material-symbols-outlined text-sm">delete</span>
                    </button>
                  </div>
                ))}

                {state.savedDiscoveries.length > 4 && (
                  <button
                    onClick={() => setShowLikedGamesModal(true)}
                    className="w-full py-2.5 mt-2 border border-outline-variant text-sm font-semibold hover:bg-surface-container-highest hover:text-primary transition-colors uppercase tracking-wider rounded-sm flex items-center justify-center gap-2 group cursor-pointer btn-interactive"
                  >
                    View All ({state.savedDiscoveries.length})
                    <span className="material-symbols-outlined text-[16px] group-hover:translate-x-1 transition-transform">
                      arrow_forward
                    </span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column (col-span-2) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Generated Games Panel */}
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel flex-1 flex flex-col stagger-enter stagger-3">
            <div className="absolute -top-3 -right-3 bg-tertiary text-background text-xs font-display px-2 py-1 uppercase tracking-wider shadow-[2px_2px_0px_#000]">
              Activity
            </div>

            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined text-tertiary">memory</span>
              <h2 className="font-display text-lg uppercase tracking-wide">Generated Games</h2>
            </div>

            {state.authStatus !== 'AUTHENTICATED' ? (
              <div className="text-on-surface-variant font-mono text-xs border border-outline-variant p-6 text-center space-y-3">
                <p>Log in to view your generated game prototypes.</p>
                <button
                  onClick={() => openAuthModal('login')}
                  className="px-4 py-2 bg-primary text-on-primary font-mono text-xs uppercase rounded-sm btn-interactive glow-cyan cursor-pointer"
                >
                  Sign In
                </button>
              </div>
            ) : state.myGames.length === 0 ? (
              <div className="text-on-surface-variant font-mono text-xs border border-outline-variant p-6 text-center">
                No games generated yet. Create your first prototype in the Scene Composer!
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-auto">
                {state.myGames.slice(0, 4).map((game) => (
                  <div
                    key={game.id}
                    className="bg-surface border border-outline-variant p-4 flex flex-col rounded-sm relative overflow-hidden group hover:border-tertiary/50 transition-colors"
                  >
                    <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-tertiary/10 to-transparent pointer-events-none"></div>
                    <div className="flex justify-between items-start mb-3">
                      <h3 className="font-bold text-lg group-hover:text-tertiary transition-colors truncate max-w-[180px]" title={game.title}>{game.title}</h3>
                      <span className="bg-surface-container-highest text-xs px-2 py-0.5 rounded border border-outline-variant/50 font-mono text-tertiary">
                        {game.status}
                      </span>
                    </div>
                    <p className="text-sm text-on-surface-variant line-clamp-3 mb-4 flex-1">{game.prompt}</p>
                    <div className="flex flex-wrap gap-2 mb-4">
                      <span className="text-xs bg-surface-container-highest px-2 py-1 rounded-sm border border-outline-variant/30">
                        {game.genre}
                      </span>
                      <span className="text-xs bg-surface-container-highest px-2 py-1 rounded-sm border border-outline-variant/30">
                        {game.parameters.engine}
                      </span>
                    </div>
                    <div className="flex gap-4">
                      <button
                        onClick={() => setSelectedPlayProject(game)}
                        className="flex items-center gap-2 text-sm text-tertiary hover:text-primary transition-colors font-semibold uppercase tracking-wider cursor-pointer btn-interactive origin-left"
                      >
                        <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                        Play
                      </button>
                      <button
                        onClick={() => handleContinueEdit(game.prompt)}
                        className="flex items-center gap-2 text-sm text-primary hover:text-tertiary transition-colors font-semibold uppercase tracking-wider cursor-pointer btn-interactive origin-left"
                      >
                        <span className="material-symbols-outlined text-[18px]">edit_document</span>
                        Edit
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedPlayProject && (
        <PrototypeModal
          project={selectedPlayProject}
          onClose={() => setSelectedPlayProject(null)}
          onProjectUpdated={updateGameProject}
        />
      )}

      {showLikedGamesModal &&
        createPortal(
          <div
            className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm ${
              isClosingModal ? 'modal-backdrop-exit' : 'modal-backdrop-enter'
            }`}
            onClick={(e) => {
              if (e.target === e.currentTarget && !isClosingModal) handleCloseModal();
            }}
          >
            <div
              className={`w-full max-w-lg max-h-[90vh] overflow-y-auto bg-surface border-2 border-secondary rounded-sm flex flex-col shadow-[0_0_30px_rgba(255,107,181,0.2)] ${
                isClosingModal ? 'modal-exit' : 'modal-enter'
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="bg-terminal-header border-b border-secondary/30 p-3 flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2 text-secondary">
                  <span className="material-symbols-outlined">favorite</span>
                  <span className="font-mono text-sm tracking-widest font-bold uppercase">All Saved Discoveries</span>
                </div>
                <button
                  onClick={handleCloseModal}
                  className="text-on-surface-variant hover:text-secondary p-1 icon-interactive cursor-pointer"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
              <div className="p-6 bg-terminal-bg max-h-[60vh] overflow-y-auto space-y-3">
                {state.savedDiscoveries.map((sd) => (
                  <div key={sd.id} className="flex items-center justify-between p-3 bg-surface border border-outline-variant rounded-sm">
                    <div>
                      <h4 className="font-mono text-xs text-primary font-bold">{sd.title}</h4>
                      <p className="font-mono text-[10px] text-on-surface-variant">{sd.genres.join(', ') || 'Game'}</p>
                    </div>
                    <button
                      onClick={() => removeSavedDiscovery(sd.id)}
                      className="text-error hover:underline font-mono text-xs cursor-pointer"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
