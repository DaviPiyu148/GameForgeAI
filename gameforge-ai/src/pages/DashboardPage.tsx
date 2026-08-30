import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';
import { ProjectDetailsModal } from '../components/Shared/ProjectDetailsModal';
import { ProjectCoverArt } from '../components/Shared/ProjectCoverArt';
import { projectService } from '../services/projects';
import { pushToast } from '../services/toastBus';
import type { GameProject } from '../types';

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
        autoFocus
        className="flex-1 bg-terminal-bg border border-primary/60 text-primary font-display text-base uppercase px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-primary min-w-0"
        value={value}
        maxLength={255}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === 'NumpadEnter') { e.preventDefault(); handleSave(); }
          if (e.key === 'Escape') { onCancel(); }
        }}
        onBlur={() => {
          // Blur → save if changed, else cancel
          const trimmed = value.trim();
          if (trimmed && trimmed !== initialTitle) { handleSave(); } else { onCancel(); }
        }}
        disabled={saving}
        aria-label="Rename project"
      />
      <button
        onClick={handleSave}
        disabled={saving || !value.trim()}
        className="text-primary hover:text-on-primary hover:bg-primary p-1 transition-colors cursor-pointer rounded-sm"
        title="Save name (Enter)"
      >
        <span className="material-symbols-outlined text-[14px]">check</span>
      </button>
      <button
        onClick={onCancel}
        className="text-on-surface-variant hover:text-error p-1 transition-colors cursor-pointer rounded-sm"
        title="Cancel (Esc)"
      >
        <span className="material-symbols-outlined text-[14px]">close</span>
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
    updateGameProject,
    deleteProject,
    duplicateProject,
  } = useAppContext();
  const navigate = useNavigate();

  const [selectedPlayProject, setSelectedPlayProject] = useState<GameProject | null>(null);
  const [detailsProject, setDetailsProject] = useState<GameProject | null>(null);

  // Per-card UI state: rename / delete confirm / duplicating
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);
  // Per-card contextual action menu
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const handleContinueEditing = (game: GameProject) => {
    setPrompt(game.prompt);
    updateBuildParams(game.parameters);
    navigate('/build');
  };

  const handleRemix = (game: GameProject) => {
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
      <header className="flex flex-col gap-1 border-l-4 border-primary pl-4 py-1">
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
                    {renamingId === game.id ? (
                      <RenameInput
                        initialTitle={game.title}
                        onSave={(t) => handleRename(game.id, t)}
                        onCancel={() => setRenamingId(null)}
                      />
                    ) : (
                      <h3
                        className="font-display text-base md:text-lg text-primary uppercase truncate max-w-[200px] cursor-pointer hover:text-primary/80 transition-colors"
                        title={`${game.title} (click to rename)`}
                        onClick={() => { setRenamingId(game.id); setOpenMenuId(null); }}
                      >
                        {game.title}
                      </h3>
                    )}
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

                {/* ── Delete confirmation (shown instead of buttons when active) ── */}
                {deleteConfirmId === game.id ? (
                  <DeleteConfirm
                    title={game.title}
                    onConfirm={() => handleDeleteConfirm(game.id)}
                    onCancel={() => setDeleteConfirmId(null)}
                    isDeleting={deletingId === game.id}
                  />
                ) : (
                  /* ── Action bar ── */
                  <div className="flex gap-2 mt-auto">
                    {/* Primary: PLAY */}
                    <button
                      onClick={() => setSelectedPlayProject(game)}
                      className="flex-1 bg-primary text-on-primary font-mono text-xs py-2 uppercase shadow-[0_0_10px_rgba(76,224,210,0.2)] cursor-pointer btn-interactive energy-sweep glow-cyan"
                    >
                      PLAY
                    </button>

                    {/* Secondary: CONTINUE EDITING */}
                    <button
                      onClick={() => handleContinueEditing(game)}
                      className="flex-1 border border-primary text-primary font-mono text-xs py-2 hover:bg-primary/10 uppercase cursor-pointer btn-interactive"
                    >
                      EDIT
                    </button>

                    {/* Contextual: ⋮ menu */}
                    <div className="relative">
                      <button
                        id={`menu-btn-${game.id}`}
                        onClick={() => setOpenMenuId(openMenuId === game.id ? null : game.id)}
                        className="border border-outline-variant text-on-surface-variant px-2 py-2 hover:text-primary hover:border-primary uppercase cursor-pointer btn-interactive transition-colors flex items-center"
                        title="More actions"
                        aria-haspopup="true"
                        aria-expanded={openMenuId === game.id}
                      >
                        <span className="material-symbols-outlined text-[18px]">more_vert</span>
                      </button>

                      {openMenuId === game.id && (
                        <>
                          {/* Click-away backdrop */}
                          <div className="fixed inset-0 z-20" onClick={() => setOpenMenuId(null)} />
                          <div className="absolute right-0 bottom-full mb-1 w-44 bg-surface-container border border-primary/40 shadow-xl z-30 flex flex-col modal-enter rounded-sm overflow-hidden">
                            <button
                              onClick={() => { setRenamingId(game.id); setOpenMenuId(null); }}
                              className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left"
                            >
                              <span className="material-symbols-outlined text-[14px]">edit</span>
                              Rename
                            </button>
                            <button
                              onClick={() => handleRemix(game)}
                              className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left"
                            >
                              <span className="material-symbols-outlined text-[14px]">shuffle</span>
                              Remix
                            </button>
                            <button
                              onClick={() => handleDuplicate(game.id)}
                              disabled={duplicatingId === game.id}
                              className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left disabled:opacity-50"
                            >
                              <span className="material-symbols-outlined text-[14px]">content_copy</span>
                              {duplicatingId === game.id ? 'Duplicating…' : 'Duplicate'}
                            </button>
                            <button
                              onClick={() => { setDetailsProject(game); setOpenMenuId(null); }}
                              className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer text-left"
                            >
                              <span className="material-symbols-outlined text-[14px]">info</span>
                              Details
                            </button>
                            <div className="border-t border-outline-variant/50 my-0.5" />
                            <button
                              onClick={() => { setDeleteConfirmId(game.id); setOpenMenuId(null); }}
                              className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] text-error/80 hover:bg-error/10 hover:text-error transition-colors cursor-pointer text-left"
                            >
                              <span className="material-symbols-outlined text-[14px]">delete</span>
                              Delete
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ═══ SAVED DISCOVERIES ═══ */}
      <section className="flex flex-col gap-4 mt-4">
        <div className="flex items-center gap-2 border-b border-outline-variant pb-2">
          <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>
            bookmark
          </span>
          <h2 className="font-mono text-xs text-secondary uppercase tracking-widest">SAVED DISCOVERIES</h2>
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
          <div className="text-on-surface-variant font-mono text-xs border border-outline-variant bg-surface-container-low p-6 text-center">
            No saved discoveries yet. Bookmark interesting games found on the Discover page!
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 stagger-enter stagger-2">
            {state.savedDiscoveries.map((discovery, index) => (
              <div
                key={discovery.id}
                className={`bg-surface-container border-2 border-outline-variant flex flex-col relative overflow-hidden stagger-enter stagger-${
                  (index % 5) + 1
                } hover:border-secondary/50 transition-colors group`}
              >
                <div className="h-4 bg-outline-variant w-full flex justify-between px-2 items-center">
                  <div className="flex gap-1">
                    <div className="w-1 h-1 bg-background rounded-full"></div>
                    <div className="w-1 h-1 bg-background rounded-full"></div>
                  </div>
                  <button
                    onClick={() => removeSavedDiscovery(discovery.id)}
                    className="text-on-surface-variant hover:text-error text-[10px] font-mono cursor-pointer"
                    title="Delete bookmark"
                    aria-label="Delete bookmark"
                  >
                    ×
                  </button>
                </div>
                <div className="p-3 flex flex-col gap-2 h-full">
                  <div className="aspect-video bg-surface-dim border border-outline-variant overflow-hidden flex items-center justify-center">
                    <span className="material-symbols-outlined text-2xl text-secondary/40">
                      sports_esports
                    </span>
                  </div>
                  <h4 className="font-mono text-xs text-on-surface uppercase truncate mt-1 font-bold" title={discovery.title}>
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

      {selectedPlayProject && (
        <PrototypeModal
          project={selectedPlayProject}
          onClose={() => setSelectedPlayProject(null)}
          onProjectUpdated={updateGameProject}
        />
      )}
      {detailsProject && (
        <ProjectDetailsModal
          project={detailsProject}
          onClose={() => setDetailsProject(null)}
        />
      )}
    </div>
  );
};

export default DashboardPage;
