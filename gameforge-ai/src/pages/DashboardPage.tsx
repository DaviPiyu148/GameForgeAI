import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';
import { ProjectStudioModal, type StudioTabId } from '../components/Shared/ProjectStudioModal';
import { ProjectCoverArt } from '../components/Shared/ProjectCoverArt';
import { SavedDiscoveryCover } from '../components/Shared/SavedDiscoveryCover';
import { GameDetailsModal } from '../components/Shared/GameDetailsModal';
import { projectService } from '../services/projects';
import { inspirationService } from '../services/inspirations';
import { pushToast } from '../services/toastBus';
import { buildDiscoverySeed } from '../utils/discovery';
import type { GameProject, ProjectVersionSummary, DiscoverySearchResult } from '../types';

// ─────────────────────────────────────────────────────────
// Inline Rename component — lives inside each card
// ─────────────────────────────────────────────────────────
interface RenameInputProps {
  initialTitle: string;
  onSave: (newTitle: string) => void;
  onCancel: () => void;
}
function RenameInput({ initialTitle, onSave, onCancel }: RenameInputProps) {
  const [value, setValue] = useState(initialTitle);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSave = useCallback(async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === initialTitle) { onCancel(); return; }
    if (trimmed.length > 255) { return; }
    setSaving(true);
    onSave(trimmed);
  }, [value, initialTitle, onSave, onCancel]);

  return (
    <div className="flex items-center gap-1 w-full">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); handleSave(); }
          if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
        }}
        disabled={saving}
        className="flex-1 bg-terminal-bg border border-primary/60 text-primary font-mono text-xs px-2 py-1 outline-none rounded-xs focus:ring-1 focus:ring-primary"
        autoFocus
        maxLength={255}
      />
      <button
        onClick={handleSave}
        disabled={saving}
        className="px-2 py-1 bg-primary text-on-primary font-mono text-[10px] uppercase font-bold rounded-xs cursor-pointer hover:bg-primary-bright disabled:opacity-50"
      >
        {saving ? '…' : '✓'}
      </button>
      <button
        onClick={onCancel}
        disabled={saving}
        className="px-2 py-1 border border-outline-variant text-on-surface-variant font-mono text-[10px] uppercase rounded-xs cursor-pointer hover:text-white disabled:opacity-50"
      >
        ✕
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Delete confirmation widget — inline in the card
// ─────────────────────────────────────────────────────────
interface DeleteConfirmProps {
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}
function DeleteConfirm({ title, onConfirm, onCancel, isDeleting }: DeleteConfirmProps) {
  return (
    <div className="bg-error/10 border border-error/40 p-2 flex flex-col gap-2 rounded-sm">
      <p className="font-mono text-[10px] text-error uppercase leading-tight">
        Permanently delete "{title}"?<br />This cannot be undone.
      </p>
      <div className="flex gap-2">
        <button
          onClick={onConfirm}
          disabled={isDeleting}
          className="flex-1 bg-error text-white font-mono text-[10px] uppercase py-1.5 hover:bg-error/80 cursor-pointer btn-interactive transition-colors disabled:opacity-50"
        >
          {isDeleting ? 'Deleting…' : 'Delete'}
        </button>
        <button
          onClick={onCancel}
          disabled={isDeleting}
          className="flex-1 border border-outline-variant text-on-surface-variant font-mono text-[10px] uppercase py-1.5 hover:text-primary hover:border-primary cursor-pointer btn-interactive transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Main DashboardPage
// ─────────────────────────────────────────────────────────
const DashboardPage = () => {
  const {
    state,
    setPrompt,
    updateBuildParams,
    openAuthModal,
    removeSavedDiscovery,
    saveDiscovery,
    updateGameProject,
    deleteProject,
    duplicateProject,
    searchDiscovery,
    clearBuildInspiration,
    setPendingInspirationTarget,
  } = useAppContext();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedPlayProject, setSelectedPlayProject] = useState<GameProject | null>(null);
  const [playModalInitialTab, setPlayModalInitialTab] = useState<'play' | 'remix'>('play');
  const [playbackVersion, setPlaybackVersion] = useState<ProjectVersionSummary | null>(null);
  const [studioProject, setStudioProject] = useState<GameProject | null>(null);
  const [studioInitialTab, setStudioInitialTab] = useState<StudioTabId>('overview');
  const [selectedSavedGame, setSelectedSavedGame] = useState<DiscoverySearchResult | null>(null);

  // Per-card UI state: rename / delete confirm / duplicating / attaching inspiration
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);
  const [attachingInspirationId, setAttachingInspirationId] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuContainerRef = useRef<HTMLDivElement | null>(null);

  const handleOpenStudio = useCallback((game: GameProject, initialTab: StudioTabId = 'overview') => {
    setOpenMenuId(null);
    setSelectedPlayProject(null);
    setPlaybackVersion(null);
    setStudioInitialTab(initialTab);
    setStudioProject(game);
  }, []);

  const handleAttachPendingInspiration = async (game: GameProject) => {
    if (!state.pendingInspirationTarget) return;
    const target = state.pendingInspirationTarget;
    const targetTitle = target.game.display_title || target.game.title;
    const steamAppId = target.game.external_id || target.game.id;

    if (!steamAppId) {
      pushToast({
        variant: 'error',
        title: 'ATTACH FAILED',
        description: 'Selected game does not have an external identifier.',
      });
      return;
    }

    setAttachingInspirationId(game.id);
    try {
      await inspirationService.attach(game.id, steamAppId);
      pushToast({
        variant: 'success',
        title: 'INSPIRATION ATTACHED',
        description: `"${targetTitle}" was attached to "${game.title}".`,
      });
      setPendingInspirationTarget(null);
      handleOpenStudio(game, 'overview');
    } catch (err: unknown) {
      const isDuplicate =
        (err && typeof err === 'object' && 'code' in err && (err as { code: string }).code === 'ALREADY_INSPIRED') ||
        (err instanceof Error && err.message.toLowerCase().includes('already attached'));

      if (isDuplicate) {
        pushToast({
          variant: 'info',
          title: 'ALREADY ATTACHED',
          description: `"${targetTitle}" is already in "${game.title}"'s inspiration deck.`,
        });
        setPendingInspirationTarget(null);
        handleOpenStudio(game, 'overview');
      } else {
        const msg = err instanceof Error ? err.message : 'Could not attach inspiration to project.';
        pushToast({
          variant: 'error',
          title: 'ATTACH FAILED',
          description: msg,
        });
      }
    } finally {
      setAttachingInspirationId(null);
    }
  };

  // Auto-open Studio when navigating with ?studio=<projectId>
  useEffect(() => {
    const studioParam = searchParams.get('studio');
    if (studioParam && state.myGames.length > 0) {
      const target = state.myGames.find((p) => p.id === studioParam);
      if (target) {
        handleOpenStudio(target, 'overview');
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.delete('studio');
          return next;
        }, { replace: true });
      }
    }
  }, [searchParams, state.myGames, handleOpenStudio, setSearchParams]);

  // Global click-outside & Escape dismiss for 3-dots dropdown
  useEffect(() => {
    if (!openMenuId) return;

    const handlePointerDownOutside = (e: MouseEvent) => {
      if (menuContainerRef.current && menuContainerRef.current.contains(e.target as Node)) {
        return;
      }
      setOpenMenuId(null);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpenMenuId(null);
      }
    };

    document.addEventListener('mousedown', handlePointerDownOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDownOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [openMenuId]);

  const openSavedGameDetails = (discovery: typeof state.savedDiscoveries[0]) => {
    const existingResult = (state.discoveryResults || []).find(
      (r) => (r.game.external_id || r.game.id) === discovery.steam_app_id
    );
    const steamCapsule = discovery.steam_app_id
      ? `https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/${discovery.steam_app_id}/header.jpg`
      : undefined;

    const resultToOpen: DiscoverySearchResult = existingResult ?? {
      game: {
        id: discovery.steam_app_id || discovery.id,
        external_id: discovery.steam_app_id || discovery.id,
        source: 'steam',
        title: discovery.title,
        display_title: discovery.title,
        description: `Saved game from your curated collection: ${discovery.title}.`,
        genres: discovery.genres,
        display_genres: discovery.genres,
        tags: discovery.genres,
        player_modes: ['Single-player'],
        platforms: ['Windows'],
        release_year: 2024,
        is_free: false,
        cover_image_url: steamCapsule,
        hero_image_url: steamCapsule,
      },
      score: 1.0,
      match_highlights: ['Saved in collection'],
      explanation: 'In your curated saved games library',
    };
    setSelectedSavedGame(resultToOpen);
  };

  const handlePlay = (game: GameProject) => {
    setStudioProject(null);
    setPlaybackVersion(null);
    setPlayModalInitialTab('play');
    setSelectedPlayProject(game);
  };

  const handleDirectRemix = (game: GameProject) => {
    setOpenMenuId(null);
    setStudioProject(null);
    setPlaybackVersion(null);
    setPlayModalInitialTab('remix');
    setSelectedPlayProject(game);
  };

  const handleDiscoverSimilar = (game: GameProject) => {
    setOpenMenuId(null);
    const seed = buildDiscoverySeed(game);
    searchDiscovery(seed, navigate, 'BEST_MATCH');
  };

  const handleContinueEditing = (game: GameProject) => {
    clearBuildInspiration();
    setPrompt(game.prompt);
    updateBuildParams(game.parameters);
    navigate('/build');
  };

  const handleRename = async (gameId: string, newTitle: string) => {
    try {
      const updated = await projectService.updateProject(gameId, { title: newTitle });
      updateGameProject(updated);
      pushToast({ variant: 'success', title: 'RENAMED', description: `Renamed to "${updated.title}".` });
    } catch (err) {
      pushToast({ variant: 'error', title: 'RENAME FAILED', description: 'Could not save the new name. Please try again.' });
      console.warn('Rename failed', err);
    } finally {
      setRenamingId(null);
    }
  };

  const handleDuplicate = async (gameId: string) => {
    setOpenMenuId(null);
    setDuplicatingId(gameId);
    try {
      await duplicateProject(gameId);
    } catch (err) {
      pushToast({ variant: 'error', title: 'DUPLICATE FAILED', description: 'Could not duplicate this project.' });
      console.warn('Duplicate failed', err);
    } finally {
      setDuplicatingId(null);
    }
  };

  const handleDeleteConfirm = async (gameId: string) => {
    setDeletingId(gameId);
    try {
      await deleteProject(gameId);
      setDeleteConfirmId(null);
    } catch (err) {
      pushToast({ variant: 'error', title: 'DELETE FAILED', description: 'Could not delete this project.' });
      console.warn('Delete failed', err);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-8">
      {/* Header */}
      <header className="flex flex-col gap-1 border-b border-primary/30 pb-3">
        <div className="flex items-center gap-2 text-primary font-mono text-xs uppercase tracking-widest">
          <span className="material-symbols-outlined text-sm">terminal</span>
          <span>SYSTEM_STORAGE // REPOSITORY_INDEX</span>
        </div>
        <h1 className="font-display text-base md:text-2xl text-on-surface uppercase tracking-tight">
          MY GAMES DASHBOARD
        </h1>
        <p className="font-mono text-xs text-on-surface-variant uppercase">
          Your generated prototypes and saved discoveries.
        </p>
      </header>

      {/* ═══ GENERATED BY YOU ═══ */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-outline-variant pb-2">
          <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>
            terminal
          </span>
          <h2 className="font-mono text-xs text-secondary uppercase tracking-widest">GENERATED BY YOU</h2>
        </div>

        {/* ═══ PENDING INSPIRATION BANNER ═══ */}
        {state.pendingInspirationTarget && (
          <div className="bg-primary/10 border-2 border-primary p-4 rounded-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-[0_0_25px_rgba(76,224,210,0.25)] animate-fade-in">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-3xl text-primary animate-pulse shrink-0">
                lightbulb
              </span>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs text-primary font-bold tracking-widest uppercase">
                    ATTACHING INSPIRATION
                  </span>
                  <span className="font-mono text-[10px] text-on-surface-variant">
                    [App ID: {state.pendingInspirationTarget.game.external_id || state.pendingInspirationTarget.game.id}]
                  </span>
                </div>
                <p className="font-display text-base text-white">
                  {state.pendingInspirationTarget.game.display_title || state.pendingInspirationTarget.game.title}
                </p>
                <p className="font-mono text-xs text-on-surface-variant">
                  Select an existing project below to attach this game as a design reference in Studio.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setPendingInspirationTarget(null)}
              className="px-3 py-1.5 border border-outline-variant hover:border-on-surface text-on-surface-variant hover:text-white font-mono text-xs uppercase rounded cursor-pointer self-end md:self-center"
            >
              Cancel
            </button>
          </div>
        )}

        {state.authStatus !== 'AUTHENTICATED' ? (
          <div className="text-on-surface-variant font-mono text-xs border border-outline-variant bg-surface-container-low p-8 text-center space-y-3">
            <p>You are browsing as an unauthenticated guest. Sign in to view and persist your generated games.</p>
            <button
              onClick={() => openAuthModal('login')}
              className="px-6 py-2.5 bg-primary text-on-primary font-mono text-xs uppercase rounded-sm btn-interactive glow-cyan cursor-pointer inline-flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-sm">login</span>
              <span>Sign In to Access Projects</span>
            </button>
          </div>
        ) : state.isProjectsLoading ? (
          <div className="text-primary font-mono text-xs border border-primary/30 bg-surface-container-low p-6 text-center animate-pulse">
            &gt; SYNCING_BACKEND_PROJECTS...
          </div>
        ) : state.myGames.length === 0 ? (
          <div className="text-on-surface-variant font-mono text-xs border border-outline-variant bg-surface-container-low p-6 text-center">
            No games generated yet. Head to the Builder to build one!
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 stagger-enter stagger-1">
            {state.myGames.map((game, index) => (
              <div
                key={game.id}
                className={`bg-surface-container-low border border-primary/50 p-4 flex flex-col gap-3 relative overflow-hidden group hover:border-primary hover:-translate-y-1 hover:shadow-[0_0_20px_rgba(76,224,210,0.3)] transition-all duration-300 stagger-enter stagger-${(index % 5) + 1}`}
              >
                {/* ── Corner decoration ── */}
                <div className="absolute top-0 right-0 p-2 opacity-10 font-mono text-[10px] pointer-events-none group-hover:opacity-20 transition-opacity">
                  SYS.ID: {game.id.substring(0, 6).toUpperCase()}
                  <br />
                  MEM_ADDR: 0x00FF
                </div>

                {/* ── Title row ── */}
                <div className="flex justify-between items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {renamingId === game.id ? (
                        <RenameInput
                          initialTitle={game.title}
                          onSave={(t) => handleRename(game.id, t)}
                          onCancel={() => setRenamingId(null)}
                        />
                      ) : (
                        <h3 className="font-display text-base md:text-lg text-primary uppercase truncate max-w-[200px]">
                          <button
                            type="button"
                            onClick={() => { setRenamingId(game.id); setOpenMenuId(null); }}
                            className="truncate max-w-full text-left cursor-pointer hover:text-primary/80 transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded-xs"
                            aria-label={`Rename project ${game.title}`}
                            title={`${game.title} (click to rename)`}
                          >
                            {game.title}
                          </button>
                        </h3>
                      )}
                      {game.currentVersion && game.currentVersion > 1 && (
                        <span className="bg-primary/10 border border-primary/30 text-primary font-mono text-[9px] px-1.5 py-0.5 rounded-xs font-bold shrink-0">
                          v{game.currentVersion}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="font-mono text-[10px] text-outline border border-outline px-1">
                        &gt; v{game.currentVersion ?? 1}.0
                      </span>
                      <span className="font-mono text-[10px] text-on-surface-variant">{game.genre}</span>
                      <span className="font-mono text-[10px] text-outline ml-4">Modified: {game.lastModified}</span>
                    </div>
                  </div>

                  {/* Status badge */}
                  <div
                    className={`flex items-center gap-1 border px-2 py-1 shrink-0 ${
                      game.status === 'ERROR'
                        ? 'bg-error/10 border-error/40'
                        : game.status === 'COMPILING'
                        ? 'bg-tertiary/10 border-tertiary/40'
                        : 'bg-primary/10 border-primary/30'
                    }`}
                  >
                    <div
                      className={`w-2 h-2 rounded-full ${
                        game.status === 'ERROR'
                          ? 'bg-error ai-pulse'
                          : game.status === 'COMPILING'
                          ? 'bg-tertiary ai-pulse'
                          : 'bg-primary'
                      }`}
                    />
                    <span
                      className={`font-mono text-[10px] uppercase ${
                        game.status === 'ERROR' ? 'text-error' : game.status === 'COMPILING' ? 'text-tertiary' : 'text-primary'
                      }`}
                    >
                      {game.status}
                    </span>
                  </div>
                </div>

                {/* ── Cover Art ── */}
                <ProjectCoverArt project={game} className="h-32 w-full border border-outline-variant" />

                {/* ── Pending Inspiration Attach CTA or Normal Action Bar ── */}
                {state.pendingInspirationTarget ? (
                  <button
                    type="button"
                    onClick={() => handleAttachPendingInspiration(game)}
                    disabled={attachingInspirationId === game.id}
                    className="w-full h-10 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded btn-interactive energy-sweep glow-cyan flex items-center justify-center gap-2 cursor-pointer shadow-lg disabled:opacity-60"
                  >
                    <span className="material-symbols-outlined text-sm">
                      {attachingInspirationId === game.id ? 'progress_activity' : 'lightbulb'}
                    </span>
                    <span>
                      {attachingInspirationId === game.id
                        ? 'Attaching Inspiration...'
                        : `Attach to "${game.title}"`}
                    </span>
                  </button>
                ) : deleteConfirmId === game.id ? (
                  <DeleteConfirm
                    title={game.title}
                    onConfirm={() => handleDeleteConfirm(game.id)}
                    onCancel={() => setDeleteConfirmId(null)}
                    isDeleting={deletingId === game.id}
                  />
                ) : (
                  /* ── Action bar ── */
                  <div className="flex gap-1.5 mt-auto items-center">
                    {/* Primary: PLAY */}
                    <button
                      onClick={() => handlePlay(game)}
                      className="h-9 flex-1 bg-primary text-on-primary font-mono text-xs font-bold uppercase rounded shadow-[0_0_10px_rgba(76,224,210,0.2)] cursor-pointer btn-interactive energy-sweep glow-cyan inline-flex items-center justify-center gap-1"
                    >
                      <span className="material-symbols-outlined text-sm">play_arrow</span>
                      <span>PLAY</span>
                    </button>

                    {/* Secondary: STUDIO */}
                    <button
                      onClick={() => handleOpenStudio(game)}
                      className="h-9 px-3 border border-primary/60 text-primary font-mono text-xs font-bold hover:bg-primary/10 uppercase cursor-pointer btn-interactive rounded inline-flex items-center justify-center gap-1"
                      title="Open Project Studio workspace"
                    >
                      <span className="material-symbols-outlined text-sm">developer_board</span>
                      <span>STUDIO</span>
                    </button>

                    {/* Tertiary: REMIX */}
                    <button
                      onClick={() => handleDirectRemix(game)}
                      className="h-9 flex-1 border border-secondary text-secondary font-mono text-xs font-bold hover:bg-secondary/10 uppercase cursor-pointer btn-interactive rounded inline-flex items-center justify-center gap-1"
                      title="Directly remix and evolve this game"
                    >
                      <span className="material-symbols-outlined text-sm">shuffle</span>
                      <span>REMIX</span>
                    </button>

                    {/* Discover Similar icon button */}
                    <button
                      type="button"
                      onClick={() => handleDiscoverSimilar(game)}
                      className="h-9 w-9 border border-outline-variant text-on-surface-variant hover:text-primary hover:border-primary uppercase cursor-pointer btn-interactive rounded transition-colors inline-flex items-center justify-center shrink-0"
                      title="Discover similar games from catalog"
                      aria-label={`Discover games similar to ${game.title}`}
                    >
                      <span className="material-symbols-outlined text-sm">explore</span>
                    </button>

                    {/* Contextual: ⋮ menu */}
                    <div className="relative" ref={openMenuId === game.id ? menuContainerRef : undefined}>
                      <button
                        id={`menu-btn-${game.id}`}
                        type="button"
                        onClick={() => setOpenMenuId(openMenuId === game.id ? null : game.id)}
                        className={`h-9 w-9 border rounded uppercase cursor-pointer btn-interactive transition-colors inline-flex items-center justify-center shrink-0 ${
                          openMenuId === game.id
                            ? 'border-primary text-primary bg-primary/10'
                            : 'border-outline-variant text-on-surface-variant hover:text-primary hover:border-primary'
                        }`}
                        title="More actions"
                        aria-label={`More actions for ${game.title}`}
                        aria-expanded={openMenuId === game.id}
                        aria-controls={`actions-dropdown-${game.id}`}
                      >
                        <span className="material-symbols-outlined text-sm" aria-hidden="true">more_vert</span>
                      </button>

                      {openMenuId === game.id && (
                        <div
                          id={`actions-dropdown-${game.id}`}
                          className="absolute right-0 bottom-full mb-1 w-44 bg-surface-container border border-primary/40 shadow-xl z-30 flex flex-col modal-enter rounded-sm overflow-hidden"
                        >
                          <button
                            type="button"
                            onClick={() => { handleContinueEditing(game); setOpenMenuId(null); }}
                            className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left"
                          >
                            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">edit</span>
                            Edit in Builder
                          </button>
                          <button
                            type="button"
                            onClick={() => { setRenamingId(game.id); setOpenMenuId(null); }}
                            className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left"
                          >
                            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">label</span>
                            Rename
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDuplicate(game.id)}
                            disabled={duplicatingId === game.id}
                            className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left disabled:opacity-50"
                          >
                            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">content_copy</span>
                            {duplicatingId === game.id ? 'Duplicating…' : 'Duplicate'}
                          </button>
                          <button
                            type="button"
                            onClick={() => { setDeleteConfirmId(game.id); setOpenMenuId(null); }}
                            className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-error hover:bg-error/10 transition-colors cursor-pointer text-left border-t border-primary/10"
                          >
                            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">delete</span>
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Saved Discoveries Section ── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 border-b border-primary/30 pb-2">
          <span className="material-symbols-outlined text-secondary text-lg">bookmark</span>
          <h2 className="font-display text-lg text-on-surface uppercase tracking-wider">
            SAVED DISCOVERIES ({state.savedDiscoveries.length})
          </h2>
        </div>

        {state.authStatus !== 'AUTHENTICATED' ? (
          <div className="text-on-surface-variant font-mono text-xs border border-outline-variant bg-surface-container-low p-6 text-center">
            Sign in to view your bookmarked Steam catalog discoveries.
          </div>
        ) : state.isSavedDiscoveriesLoading ? (
          <div className="text-primary font-mono text-xs border border-primary/30 bg-surface-container-low p-6 text-center animate-pulse">
            &gt; LOADING_SAVED_DISCOVERIES...
          </div>
        ) : state.savedDiscoveries.length === 0 ? (
          <div className="bg-surface-container-low border border-dashed border-outline-variant/60 p-8 text-center rounded-sm">
            <span className="material-symbols-outlined text-3xl text-outline mb-2">bookmark_border</span>
            <p className="font-mono text-xs text-on-surface-variant uppercase">
              No saved discoveries yet. Bookmark games from the Discovery feed to curate your inspiration library.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {state.savedDiscoveries.map((discovery) => (
              <div
                key={discovery.id}
                onClick={() => openSavedGameDetails(discovery)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openSavedGameDetails(discovery);
                  }
                }}
                role="button"
                tabIndex={0}
                className="bg-surface-container-low border border-outline-variant hover:border-secondary transition-colors p-0 rounded-sm flex flex-col justify-between overflow-hidden group cursor-pointer focus:outline-none focus:ring-1 focus:ring-secondary"
              >
                <div className="bg-terminal-header px-3 py-1.5 flex justify-between items-center border-b border-outline-variant/50">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono text-secondary font-bold uppercase">BOOKMARK</span>
                    <span className="text-[9px] font-mono text-outline">
                      {discovery.created_at ? new Date(discovery.created_at).toLocaleDateString() : 'Saved'}
                    </span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeSavedDiscovery(discovery.id);
                    }}
                    className="text-on-surface-variant hover:text-error text-[10px] font-mono cursor-pointer p-0.5"
                    title="Delete bookmark"
                    aria-label="Delete bookmark"
                  >
                    ×
                  </button>
                </div>
                <div className="p-3 flex flex-col gap-2 h-full">
                  <div className="aspect-video bg-surface-dim border border-outline-variant group-hover:border-secondary/50 transition-colors overflow-hidden flex items-center justify-center relative">
                    <SavedDiscoveryCover discovery={discovery} />
                  </div>
                  <h4 className="font-mono text-xs text-on-surface uppercase truncate mt-1 font-bold group-hover:text-secondary transition-colors" title={discovery.title}>
                    {discovery.title}
                  </h4>
                  <div className="flex justify-between items-center mt-auto">
                    <span className="font-mono text-[10px] text-outline truncate max-w-[120px]">
                      {discovery.genres.slice(0, 2).join(', ') || 'Game'}
                    </span>
                    <div className="w-2 h-2 rounded-full bg-secondary"></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Dialog Modals (Clean Swapping, Zero Nesting) ── */}
      {selectedPlayProject && (
        <PrototypeModal
          project={selectedPlayProject}
          gameDsl={playbackVersion ? playbackVersion.game_dsl : selectedPlayProject.gameDsl}
          versionNumber={playbackVersion ? playbackVersion.version_number : selectedPlayProject.currentVersion}
          isHistoricalPlayback={Boolean(
            playbackVersion && playbackVersion.version_number !== selectedPlayProject.currentVersion
          )}
          initialTab={playModalInitialTab}
          onClose={() => {
            setSelectedPlayProject(null);
            setPlayModalInitialTab('play');
          }}
          onProjectUpdated={updateGameProject}
        />
      )}
      {studioProject && (
        <ProjectStudioModal
          project={studioProject}
          initialTab={studioInitialTab}
          onClose={() => setStudioProject(null)}
          onPlayCurrent={() => {
            const p = studioProject;
            setStudioProject(null);
            setPlaybackVersion(null);
            setPlayModalInitialTab('play');
            setSelectedPlayProject(p);
          }}
          onRemix={() => {
            const p = studioProject;
            setStudioProject(null);
            setPlaybackVersion(null);
            setPlayModalInitialTab('remix');
            setSelectedPlayProject(p);
          }}
          onEditInBuilder={() => {
            const p = studioProject;
            setStudioProject(null);
            handleContinueEditing(p);
          }}
          onPlayHistoricalVersion={(ver) => {
            const p = studioProject;
            setStudioProject(null);
            setPlaybackVersion(ver);
            setSelectedPlayProject(p);
          }}
          onProjectUpdated={(updated) => {
            updateGameProject(updated);
            setStudioProject(updated);
          }}
        />
      )}
      {selectedSavedGame && (
        <GameDetailsModal
          result={selectedSavedGame}
          isSaved={state.savedDiscoveries.some(
            (sd) => sd.steam_app_id === (selectedSavedGame.game.external_id || selectedSavedGame.game.id)
          )}
          onClose={() => setSelectedSavedGame(null)}
          onSave={() => {
            if (selectedSavedGame.game.external_id) {
              saveDiscovery(selectedSavedGame.game.external_id);
            }
          }}
          onBuildSimilar={(res) => {
            setSelectedSavedGame(null);
            setPrompt(`Create a game inspired by ${res.game.title}: ${res.game.description.slice(0, 150)}`);
            navigate('/build');
          }}
          onUseAsInspiration={(res) => {
            setSelectedSavedGame(null);
            setPrompt(`Create a game inspired by ${res.game.title}`);
            navigate('/build');
          }}
        />
      )}
    </div>
  );
};

export default DashboardPage;
