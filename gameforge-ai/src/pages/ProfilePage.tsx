import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { PrototypeModal } from '../components/Shared/PrototypeModal';
import { ProjectCoverArt } from '../components/Shared/ProjectCoverArt';
import { SavedDiscoveryCover } from '../components/Shared/SavedDiscoveryCover';
import { GameDetailsModal } from '../components/Shared/GameDetailsModal';
import { discoveryService } from '../services/discovery';
import type { GameProject, DiscoverySearchResult } from '../types';


export default function ProfilePage() {
  const {
    state,
    setPrompt,
    updateBuildParams,
    openAuthModal,
    logout,
    removeSavedDiscovery,
    saveDiscovery,
    updateGameProject,
    uploadAvatar,
    deleteAvatar,
    updateUsername,
    changePassword,
    refreshProgress,
    refreshPreferences,
  } = useAppContext();
  const navigate = useNavigate();

  const [selectedPlayProject, setSelectedPlayProject] = useState<GameProject | null>(null);
  const [showLikedGamesModal, setShowLikedGamesModal] = useState(false);
  const [selectedSavedGame, setSelectedSavedGame] = useState<DiscoverySearchResult | null>(null);
  const [isClosingModal, setIsClosingModal] = useState(false);
  const [displayGames, setDisplayGames] = useState(0);

  // Avatar Management Modal
  const [showAvatarModal, setShowAvatarModal] = useState(false);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const initialFetchDoneRef = useRef(false);

  // Account Settings State
  const [newUsername, setNewUsername] = useState(state.user?.username || '');
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [isUpdatingUsername, setIsUpdatingUsername] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Sync newUsername with state.user when user changes
  useEffect(() => {
    if (state.user?.username) {
      setNewUsername(state.user.username);
    }
  }, [state.user?.username]);

  const handleSaveUsername = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newUsername.trim();
    if (!trimmed) {
      setUsernameError('Username cannot be empty.');
      return;
    }
    if (trimmed.length < 2 || trimmed.length > 50) {
      setUsernameError('Username must be between 2 and 50 characters.');
      return;
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      setUsernameError('Username may only contain letters, numbers, hyphens, and underscores.');
      return;
    }

    setIsUpdatingUsername(true);
    setUsernameError(null);
    try {
      await updateUsername(trimmed);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'message' in err ? String(err.message) : 'Failed to update username.';
      setUsernameError(msg);
    } finally {
      setIsUpdatingUsername(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPassword) {
      setPasswordError('Please enter your current password.');
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.');
      return;
    }

    setIsChangingPassword(true);
    setPasswordError(null);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'message' in err ? String(err.message) : 'Failed to change password.';
      setPasswordError(msg);
    } finally {
      setIsChangingPassword(false);
    }
  };


  // Refresh progress and preferences once on mount if authenticated
  useEffect(() => {
    if (state.authStatus === 'AUTHENTICATED' && !initialFetchDoneRef.current) {
      initialFetchDoneRef.current = true;
      refreshProgress();
      refreshPreferences();
    }
  }, [state.authStatus, refreshProgress, refreshPreferences]);

  const handleCloseModal = () => {
    setIsClosingModal(true);
    setTimeout(() => {
      setShowLikedGamesModal(false);
      setIsClosingModal(false);
    }, 250);
  };

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
      explanation: 'From your curated saved games collection',
    };
    setSelectedSavedGame(resultToOpen);
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

    return () => {
      cancelled = true;
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [state.myGames.length]);

  const handleContinueEdit = (game: import('../types').GameProject) => {
    // FS-027 fix: restore the project's actual stored parameters rather than
    // hardcoding 'Top-Down Action' defaults.  Mirrors DashboardPage.handleModify.
    setPrompt(game.prompt);
    updateBuildParams(game.parameters);
    navigate('/build');
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAvatarError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Size limit check (2MB)
    if (file.size > 2 * 1024 * 1024) {
      setAvatarError('Image file must be smaller than 2MB.');
      return;
    }

    // MIME type check
    const validTypes = ['image/png', 'image/jpeg', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setAvatarError('Only PNG, JPEG, and WebP images are supported.');
      return;
    }

    setAvatarFile(file);
    const reader = new FileReader();
    reader.onload = (loadEvt) => {
      setAvatarPreview(loadEvt.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleUploadAvatar = async () => {
    if (!avatarFile) return;
    setIsUploadingAvatar(true);
    setAvatarError(null);
    try {
      await uploadAvatar(avatarFile);
      setShowAvatarModal(false);
      setAvatarFile(null);
      setAvatarPreview(null);
    } catch (err: any) {
      setAvatarError(err?.message || 'Failed to upload image. Please try another file.');
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleDeleteAvatar = async () => {
    setIsUploadingAvatar(true);
    setAvatarError(null);
    try {
      await deleteAvatar();
      setShowAvatarModal(false);
      setAvatarFile(null);
      setAvatarPreview(null);
    } catch (err: any) {
      setAvatarError(err?.message || 'Failed to remove avatar image.');
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const username = state.user?.username || 'Guest Architect';
  const email = state.user?.email || 'Unauthenticated Session';
  const currentLevel = state.progress?.current_level || state.user?.level || 1;
  const progressData = state.progress;
  const preferencesData = state.preferences;

  return (
    <div className="w-full max-w-6xl mx-auto p-4 md:p-6 lg:p-8 space-y-6 animate-fade-in font-body text-on-surface pb-24">
      {/* Profile Header Console */}
      <div className="relative arcade-border bg-surface-container-low p-6 arcade-panel">
        <div className="absolute top-0 left-0 right-0 h-1 bg-primary/30"></div>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative z-10">
          {/* Left: Avatar and Info */}
          <div className="flex items-center gap-6">
            <div className="relative group">
              <div className="w-24 h-24 rounded-sm border-4 border-primary bg-surface-container-high flex items-center justify-center shrink-0 glow-box-cyan overflow-hidden">
                {state.user?.avatar_url ? (
                  <img
                    src={state.user.avatar_url}
                    alt={username}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="material-symbols-outlined text-primary text-[48px]">person</span>
                )}
              </div>
              {state.authStatus === 'AUTHENTICATED' && (
                <button
                  onClick={() => {
                    setAvatarError(null);
                    setAvatarFile(null);
                    setAvatarPreview(null);
                    setShowAvatarModal(true);
                  }}
                  className="absolute inset-0 bg-background/80 flex flex-col items-center justify-center text-primary opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer text-xs font-mono font-bold"
                  title="Update Profile Picture"
                >
                  <span className="material-symbols-outlined text-lg mb-0.5">photo_camera</span>
                  Change
                </button>
              )}
            </div>

            <div className="space-y-2">
              <h1 className="font-display text-xl md:text-2xl text-primary uppercase text-glow-cyan tracking-wider">
                {username}
              </h1>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2 text-tertiary text-sm md:text-base bg-tertiary/10 px-3 py-1.5 rounded-sm border border-tertiary/20 w-fit font-mono">
                  <span className="material-symbols-outlined text-[18px]">stars</span>
                  <span>Level {currentLevel} • {progressData?.creator_title || 'Novice Creator'}</span>
                </div>
                <span className="font-mono text-xs text-on-surface-variant">{email}</span>
                {state.authStatus === 'AUTHENTICATED' && (
                  <button
                    onClick={() => {
                      document.getElementById('account-settings')?.scrollIntoView({ behavior: 'smooth' });
                    }}
                    className="flex items-center gap-1 text-xs font-mono text-primary/80 hover:text-primary hover:underline cursor-pointer border border-primary/30 hover:border-primary/60 px-2.5 py-1 rounded-sm bg-primary/5 transition-colors"
                    title="Jump to Account Settings"
                  >
                    <span className="material-symbols-outlined text-sm">settings</span>
                    <span>Settings</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Right: Stat boxes & Auth Action */}
          <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
            <div className="bg-surface-container-highest h-24 p-3 border border-outline-variant flex-1 md:flex-none min-w-[130px] flex flex-col items-center justify-center text-center rounded-sm">
              <div className="text-xs text-on-surface-variant uppercase tracking-wider mb-1">Total XP</div>
              <div className="font-display text-tertiary text-base font-bold">{progressData?.total_xp || 0}</div>
            </div>
            <div className="bg-surface-container-highest h-24 p-3 border border-outline-variant flex-1 md:flex-none min-w-[130px] flex flex-col items-center justify-center text-center rounded-sm">
              <div className="text-xs text-on-surface-variant uppercase tracking-wider mb-1">Milestones</div>
              <div className="font-display text-tertiary text-base font-bold">
                {progressData?.unlocked_milestone_count || 0} / {progressData?.total_milestone_count || 8}
              </div>
            </div>
            <div className="bg-surface-container-highest h-24 p-3 border border-outline-variant flex-1 md:flex-none min-w-[130px] flex flex-col items-center justify-center text-center rounded-sm">
              <div className="text-xs text-on-surface-variant uppercase tracking-wider mb-1">Saved Items</div>
              <div className="font-display text-primary text-base font-bold">{state.savedDiscoveries.length}</div>
            </div>
            <div className="bg-surface-container-highest h-24 p-3 border border-outline-variant flex-1 md:flex-none min-w-[130px] flex flex-col items-center justify-center text-center rounded-sm">
              <div className="text-xs text-on-surface-variant uppercase tracking-wider mb-1">Games Built</div>
              <div className="font-display text-secondary text-base font-bold">{displayGames}</div>
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

      {/* Progression & XP Status Panel */}
      {state.authStatus === 'AUTHENTICATED' && (
        <div className="relative arcade-border bg-surface-container-low p-6 arcade-panel space-y-5">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-2">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary text-xl">military_tech</span>
              <h2 className="font-display text-lg uppercase tracking-wide">
                Creator Progression • Level {currentLevel} {progressData?.creator_title || 'Novice Creator'}
              </h2>
            </div>
            <div className="font-mono text-xs text-tertiary font-bold">
              {progressData?.xp_into_level || 0} / {(progressData?.xp_into_level || 0) + (progressData?.xp_needed_for_next || 100)} XP
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-1.5">
            <div className="w-full h-3.5 bg-surface-container-highest border border-outline-variant/60 rounded-sm overflow-hidden p-0.5 relative">
              <div
                className="h-full bg-gradient-to-r from-tertiary/70 via-tertiary to-primary transition-all duration-500 rounded-xs shadow-[0_0_8px_rgba(255,234,0,0.5)]"
                style={{ width: `${progressData?.progress_percentage || 0}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] font-mono text-on-surface-variant">
              <span>{progressData?.creator_title || 'Novice Creator'} (Level {currentLevel})</span>
              <span>{progressData?.xp_needed_for_next || 0} XP needed for Level {currentLevel + 1}</span>
            </div>
          </div>

          {/* Activity Rewards Breakdown */}
          <div className="grid grid-cols-2 sm:grid-cols-6 gap-2.5 pt-2">
            <div className="p-2 bg-surface border border-outline-variant/40 rounded-sm text-center">
              <div className="text-[10px] font-mono text-on-surface-variant uppercase">Search</div>
              <div className="font-mono text-xs text-primary font-bold mt-0.5">+10 XP</div>
            </div>
            <div className="p-2 bg-surface border border-outline-variant/40 rounded-sm text-center">
              <div className="text-[10px] font-mono text-on-surface-variant uppercase">Save Game</div>
              <div className="font-mono text-xs text-secondary font-bold mt-0.5">+25 XP</div>
            </div>
            <div className="p-2 bg-surface border border-outline-variant/40 rounded-sm text-center">
              <div className="text-[10px] font-mono text-on-surface-variant uppercase">Build Similar</div>
              <div className="font-mono text-xs text-primary font-bold mt-0.5">+25 XP</div>
            </div>
            <div className="p-2 bg-surface border border-outline-variant/40 rounded-sm text-center">
              <div className="text-[10px] font-mono text-on-surface-variant uppercase">Build Game</div>
              <div className="font-mono text-xs text-tertiary font-bold mt-0.5">+50 XP</div>
            </div>
            <div className="p-2 bg-surface border border-outline-variant/40 rounded-sm text-center">
              <div className="text-[10px] font-mono text-on-surface-variant uppercase">Playtest</div>
              <div className="font-mono text-xs text-tertiary font-bold mt-0.5">+35 XP</div>
            </div>
            <div className="p-2 bg-surface border border-outline-variant/40 rounded-sm text-center">
              <div className="text-[10px] font-mono text-on-surface-variant uppercase">Playtest Win</div>
              <div className="font-mono text-xs text-primary font-bold mt-0.5">+50 XP</div>
            </div>
          </div>

          {/* Creator Milestones Showcase Grid */}
          <div className="pt-4 border-t border-outline-variant/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-base">emoji_events</span>
                <h3 className="font-display text-sm uppercase tracking-wide text-white">Creator Milestones</h3>
              </div>
              <span className="font-mono text-[11px] text-tertiary font-bold bg-tertiary/10 border border-tertiary/30 px-2 py-0.5 rounded-sm">
                {progressData?.unlocked_milestone_count || 0} / {progressData?.total_milestone_count || 8} Unlocked
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {(progressData?.milestones || []).map((m) => {
                const isRecentlyUnlocked =
                  m.is_unlocked &&
                  Boolean(m.unlocked_at) &&
                  Date.now() - new Date(m.unlocked_at as string).getTime() < 10 * 60 * 1000;
                return (
                <div
                  key={m.milestone_key}
                  className={`p-3 rounded-sm border transition-all relative overflow-hidden flex flex-col justify-between hover:-translate-y-0.5 ${
                    m.is_unlocked
                      ? 'bg-surface-container border-primary/50 shadow-[0_0_10px_rgba(76,224,210,0.15)] hover:shadow-[0_0_18px_rgba(76,224,210,0.3)]'
                      : 'bg-surface-container-lowest/50 border-outline-variant/30 opacity-60'
                  } ${isRecentlyUnlocked ? 'milestone-unlock-flash' : ''}`}
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div
                        className={`w-8 h-8 rounded-sm flex items-center justify-center ${
                          m.is_unlocked
                            ? 'bg-primary/20 text-primary border border-primary/40'
                            : 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/40'
                        }`}
                      >
                        <span className="material-symbols-outlined text-base">{m.icon}</span>
                      </div>
                      <span
                        className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-xs ${
                          m.is_unlocked
                            ? 'text-primary bg-primary/10 border border-primary/30'
                            : 'text-on-surface-variant bg-surface-container border border-outline-variant/30'
                        }`}
                      >
                        {m.is_unlocked ? 'UNLOCKED' : `+${m.xp_bonus} XP`}
                      </span>
                    </div>

                    <div>
                      <h4
                        className={`font-mono text-xs font-bold ${
                          m.is_unlocked ? 'text-white' : 'text-on-surface-variant'
                        }`}
                      >
                        {m.title}
                      </h4>
                      <p className="text-[11px] font-mono text-on-surface-variant leading-tight mt-0.5">
                        {m.description}
                      </p>
                    </div>
                  </div>

                  {m.is_unlocked && m.unlocked_at && (
                    <div className="mt-2 pt-2 border-t border-primary/20 text-[10px] font-mono text-primary flex items-center gap-1">
                      <span className="material-symbols-outlined text-xs">check_circle</span>
                      <span>Unlocked {new Date(m.unlocked_at).toLocaleDateString()}</span>
                    </div>
                  )}
                </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Main Grid: Left sidebar and Right details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (col-span-1): Preferences & Saved Discoveries */}
        <div className="space-y-6">
          {/* YOUR GAME DNA Section */}
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel">
            {/* Header with Telemetry / Confidence badge */}
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl">genetics</span>
                <h2 className="font-display text-lg uppercase tracking-wide">Your Game DNA</h2>
              </div>
              {state.authStatus === 'AUTHENTICATED' && preferencesData?.has_sufficient_data ? (
                <span className="font-mono text-[10px] text-primary border border-primary/40 bg-primary/10 px-2 py-0.5 rounded-sm uppercase tracking-wider font-bold">
                  {preferencesData.confidence_level || 'MODERATE'} CONFIDENCE
                </span>
              ) : (
                <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-wider">
                  Telemetry
                </span>
              )}
            </div>

            {/* Subtitle */}
            <p className="font-mono text-[11px] text-on-surface-variant mb-4">
              Based on your GameForge activity
            </p>

            {state.authStatus !== 'AUTHENTICATED' ? (
              <div className="p-5 border border-outline-variant bg-surface-container text-center space-y-3 font-mono text-xs text-on-surface-variant">
                <span className="material-symbols-outlined text-3xl text-on-surface-variant/50">lock</span>
                <p>Sign in to build your personalized Game DNA through gameplay and discovery.</p>
                <button
                  type="button"
                  onClick={() => openAuthModal('login', 'Sign in to access your Game DNA.')}
                  className="px-4 py-2 bg-primary text-on-primary font-mono text-xs uppercase font-bold rounded-sm btn-interactive glow-cyan cursor-pointer"
                >
                  Sign In
                </button>
              </div>
            ) : !preferencesData || !preferencesData.has_sufficient_data || preferencesData.top_genres.length === 0 ? (
              /* Low-Data Forming State */
              <div className="p-5 border border-outline-variant/60 bg-surface-container text-center font-mono text-xs space-y-3 rounded-sm">
                <div className="w-10 h-10 mx-auto rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
                  <span className="material-symbols-outlined text-xl">radar</span>
                </div>
                <div className="space-y-1">
                  <h3 className="text-white font-bold uppercase text-xs">Your Game DNA is still forming</h3>
                  <p className="text-[11px] text-on-surface-variant leading-relaxed">
                    Search, save, and build games to discover your preferences.
                  </p>
                </div>
                <div className="pt-2 flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => navigate('/')}
                    className="px-3 py-1.5 border border-outline-variant hover:border-primary text-on-surface hover:text-primary text-[10px] uppercase font-bold rounded transition-colors cursor-pointer"
                  >
                    Search Games
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate('/build')}
                    className="px-3 py-1.5 bg-primary/20 hover:bg-primary/30 border border-primary/50 text-primary text-[10px] uppercase font-bold rounded transition-colors cursor-pointer"
                  >
                    Build Prototype
                  </button>
                </div>
              </div>
            ) : (
              /* Active Game DNA Representation */
              <div className="space-y-4">
                {/* Highlight Callouts Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {preferencesData.strongest_match && (
                    <div className="p-2.5 bg-primary/10 border border-primary/30 rounded-sm space-y-0.5">
                      <div className="flex items-center gap-1 text-[10px] font-mono text-primary uppercase font-bold">
                        <span className="material-symbols-outlined text-xs">stars</span>
                        <span>Strongest Match</span>
                      </div>
                      <div className="font-mono text-xs text-white font-bold truncate">
                        {preferencesData.strongest_match}
                      </div>
                    </div>
                  )}
                  {preferencesData.recent_interest && (
                    <div className="p-2.5 bg-secondary/10 border border-secondary/30 rounded-sm space-y-0.5">
                      <div className="flex items-center gap-1 text-[10px] font-mono text-secondary uppercase font-bold">
                        <span className="material-symbols-outlined text-xs">history</span>
                        <span>Recent Interest</span>
                      </div>
                      <div className="font-mono text-xs text-white font-bold truncate">
                        {preferencesData.recent_interest}
                      </div>
                    </div>
                  )}
                </div>

                {/* Ranked Genre Affinity Bars */}
                <div className="space-y-3 pt-1">
                  {preferencesData.top_genres.map((g, idx) => (
                    <div key={g.genre} className="space-y-1">
                      <div className="flex justify-between items-center text-xs font-mono">
                        <span className="text-on-surface font-semibold flex items-center gap-1.5">
                          <span className="text-on-surface-variant text-[10px]">#{idx + 1}</span>
                          <span>{g.genre}</span>
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-on-surface-variant px-1.5 py-0.2 rounded bg-surface-container-highest border border-outline-variant/40">
                            {g.affinity_tier}
                          </span>
                          <span className="text-primary font-bold">{g.percentage}%</span>
                        </div>
                      </div>
                      <div className="w-full h-2 bg-surface-container-highest rounded-xs overflow-hidden border border-outline-variant/30">
                        <div
                          className={`h-full transition-all duration-500 ${
                            idx === 0
                              ? 'bg-gradient-to-r from-primary/70 via-primary to-primary-bright shadow-[0_0_8px_rgba(76,224,210,0.4)]'
                              : idx === 1
                              ? 'bg-gradient-to-r from-secondary/70 to-secondary'
                              : 'bg-gradient-to-r from-tertiary/70 to-tertiary'
                          }`}
                          style={{ width: `${Math.max(g.percentage, 4)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Avoidances and Suggestions */}
                <div className="space-y-2 pt-2 border-t border-outline-variant/30">
                  {preferencesData.avoidances && preferencesData.avoidances.length > 0 && (
                    <div className="text-[11px] font-mono flex items-center gap-1.5 flex-wrap">
                      <span className="text-on-surface-variant uppercase font-bold text-[10px]">Avoids:</span>
                      {preferencesData.avoidances.map((a) => (
                        <span key={a} className="px-1.5 py-0.2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px]">
                          {a}
                        </span>
                      ))}
                    </div>
                  )}
                  {preferencesData.suggested_explorations && preferencesData.suggested_explorations.length > 0 && (
                    <div className="text-[11px] font-mono flex items-center gap-1.5 flex-wrap">
                      <span className="text-on-surface-variant uppercase font-bold text-[10px]">Explore:</span>
                      {preferencesData.suggested_explorations.map((e) => (
                        <span key={e} className="px-1.5 py-0.2 rounded bg-surface-container-highest border border-outline-variant/40 text-on-surface text-[10px]">
                          {e}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Reset Game DNA Control */}
                <div className="pt-2 flex justify-between items-center">
                  <span className="text-[10px] font-mono text-on-surface-variant">
                    Based on {preferencesData.total_interactions} interactions
                  </span>
                  <button
                    type="button"
                    onClick={async () => {
                      if (window.confirm('Reset your learned game preferences? Your saved games, projects, and progression will remain.')) {
                        await discoveryService.resetPreferences();
                        await refreshPreferences();
                      }
                    }}
                    className="text-[10px] font-mono text-secondary hover:text-white uppercase font-bold cursor-pointer"
                  >
                    Reset Game DNA
                  </button>
                </div>

                {/* Explanatory "How this works" footer */}
                <div className="pt-2 border-t border-outline-variant/30 flex items-start gap-2 text-[11px] font-mono text-on-surface-variant leading-relaxed">
                  <span className="material-symbols-outlined text-sm text-primary shrink-0 mt-0.5">info</span>
                  <p>
                    GameForge learns from the games you search, save, build, and play to tailor future prototype recommendations.
                  </p>
                </div>
              </div>
            )}

          </div>

          {/* Saved Discoveries Section */}
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel">
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
                    onClick={() => openSavedGameDetails(sd)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        openSavedGameDetails(sd);
                      }
                    }}
                    className="flex items-center justify-between gap-3 p-3 bg-surface-container-highest/50 border border-outline-variant/50 rounded-sm hover:bg-surface-container-highest hover:border-secondary/50 transition-colors group cursor-pointer focus:outline-none focus:ring-1 focus:ring-secondary"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-10 h-10 bg-secondary-container border border-secondary/40 rounded flex items-center justify-center shrink-0 overflow-hidden relative">
                        <SavedDiscoveryCover discovery={sd} className="w-full h-full object-cover" />
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
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSavedDiscovery(sd.id);
                      }}
                      className="p-1 text-on-surface-variant hover:text-error transition-colors cursor-pointer shrink-0"
                      title="Remove from saved"
                      aria-label="Remove from saved"
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

          {/* Recent Creator Activity Feed */}
          {state.authStatus === 'AUTHENTICATED' && (
            <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-tertiary">history</span>
                  <h2 className="font-display text-lg uppercase tracking-wide">Creator Activity</h2>
                </div>
                <span className="font-mono text-xs text-on-surface-variant">Recent Events</span>
              </div>

              {(!progressData?.recent_events || progressData.recent_events.length === 0) ? (
                <div className="p-4 border border-outline-variant/50 bg-surface-container text-center font-mono text-xs text-on-surface-variant">
                  No recent creator events recorded yet. Build and playtest games to earn XP!
                </div>
              ) : (
                <div className="space-y-2.5">
                  {progressData.recent_events.map((evt) => {
                    let iconName = 'stars';
                    let label = evt.event_type.replace(/_/g, ' ');
                    if (evt.event_type.includes('BUILD')) {
                      iconName = 'construction';
                    } else if (evt.event_type.includes('PLAYTEST')) {
                      iconName = 'sports_esports';
                    } else if (evt.event_type.includes('SAVE')) {
                      iconName = 'favorite';
                    } else if (evt.event_type.includes('SEARCH')) {
                      iconName = 'search';
                    } else if (evt.event_type.includes('MILESTONE')) {
                      iconName = 'emoji_events';
                    } else if (evt.event_type.includes('ANALYSIS') || evt.event_type.includes('IMPROVE')) {
                      iconName = 'psychology';
                    }

                    return (
                      <div
                        key={evt.id}
                        className="p-2.5 bg-surface border border-outline-variant/40 rounded-sm flex items-center justify-between gap-3 text-xs font-mono"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span className="material-symbols-outlined text-sm text-tertiary shrink-0">{iconName}</span>
                          <div className="min-w-0">
                            <div className="text-on-surface font-semibold truncate capitalize">
                              {label.toLowerCase()}
                            </div>
                            <div className="text-[10px] text-on-surface-variant">
                              {new Date(evt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {new Date(evt.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                        <span className="text-tertiary font-bold px-1.5 py-0.5 rounded bg-tertiary/10 border border-tertiary/30 shrink-0">
                          +{evt.xp_amount} XP
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column (col-span-2): Generated Games */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <div className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel flex-1 flex flex-col">
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
                No games generated yet. Create your first prototype in the Builder!
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-auto">
                {state.myGames.slice(0, 4).map((game) => (
                  <div
                    key={game.id}
                    className="bg-surface border border-outline-variant p-4 flex flex-col rounded-sm relative overflow-hidden group hover:border-tertiary/50 transition-colors"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <h3 className="font-bold text-lg group-hover:text-tertiary transition-colors truncate max-w-[180px]" title={game.title}>{game.title}</h3>
                      <span className="bg-surface-container-highest text-xs px-2 py-0.5 rounded border border-outline-variant/50 font-mono text-tertiary">
                        {game.status}
                      </span>
                    </div>
                    {/* Procedural cover thumbnail */}
                    <ProjectCoverArt project={game} className="h-24 w-full border border-outline-variant mb-3" />
                    <p className="text-sm text-on-surface-variant line-clamp-2 mb-4 flex-1">{game.prompt}</p>
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
                        onClick={() => handleContinueEdit(game)}
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

          {/* Account Settings (Username & Password) */}
          {state.authStatus === 'AUTHENTICATED' && (
            <div id="account-settings" className="relative arcade-border bg-surface-container-low p-5 md:p-6 arcade-panel">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">manage_accounts</span>
                  <h2 className="font-display text-lg uppercase tracking-wide">Account Settings</h2>
                </div>
                <span className="font-mono text-xs text-on-surface-variant">Profile & Security</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-stretch">
                {/* 1. Username Section */}
                <div className="p-4 bg-surface border border-outline-variant/60 rounded-sm flex flex-col justify-between h-full">
                  <div className="flex-1 flex flex-col">
                    <h3 className="font-mono text-xs text-primary uppercase font-bold tracking-wider mb-1 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm">badge</span>
                      Display Username
                    </h3>
                    <p className="text-[11px] text-on-surface-variant mb-4">
                      Change your public creator handle. 2–50 characters, letters, numbers, hyphens, and underscores.
                    </p>

                    <form onSubmit={handleSaveUsername} className="space-y-3 flex-1 flex flex-col justify-between">
                      <div>
                        <label htmlFor="profile-username" className="block font-mono text-[10px] uppercase text-on-surface-variant mb-1">
                          Username
                        </label>
                        <input
                          id="profile-username"
                          type="text"
                          autoComplete="username"
                          value={newUsername}
                          onChange={(e) => {
                            setNewUsername(e.target.value);
                            setUsernameError(null);
                          }}
                          className="w-full bg-terminal-bg border border-outline-variant px-3 py-2 text-on-surface font-mono text-xs focus:border-primary focus:ring-1 focus:ring-primary outline-none rounded-xs"
                          placeholder="Enter new username"
                          disabled={isUpdatingUsername}
                        />
                        {usernameError && (
                          <p role="alert" className="font-mono text-[10px] text-error mt-1">{usernameError}</p>
                        )}
                      </div>

                      <button
                        type="submit"
                        disabled={isUpdatingUsername || !newUsername.trim() || newUsername.trim() === state.user?.username}
                        className="h-9 px-4 bg-primary text-on-primary font-mono text-xs uppercase font-bold tracking-wide rounded-sm btn-interactive glow-cyan disabled:opacity-40 disabled:pointer-events-none cursor-pointer flex items-center justify-center gap-1.5 self-start"
                      >
                        {isUpdatingUsername ? (
                          <>
                            <span className="material-symbols-outlined text-sm animate-spin" aria-hidden="true">refresh</span>
                            SAVING...
                          </>
                        ) : (
                          <>
                            <span className="material-symbols-outlined text-sm" aria-hidden="true">save</span>
                            SAVE USERNAME
                          </>
                        )}
                      </button>
                    </form>
                  </div>
                </div>

                {/* 2. Password Change Section */}
                <div className="p-4 bg-surface border border-outline-variant/60 rounded-sm flex flex-col justify-between h-full">
                  <div className="flex-1 flex flex-col">
                    <h3 className="font-mono text-xs text-primary uppercase font-bold tracking-wider mb-1 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-sm" aria-hidden="true">lock</span>
                      Security & Password
                    </h3>
                    <p className="text-[11px] text-on-surface-variant mb-4">
                      Update your password. Requires current password verification.
                    </p>

                    <form onSubmit={handleChangePassword} className="space-y-3 flex-1 flex flex-col justify-between">
                      <div className="space-y-3">
                        <div>
                          <label htmlFor="profile-current-password" className="block font-mono text-[10px] uppercase text-on-surface-variant mb-1">
                            Current Password
                          </label>
                          <input
                            id="profile-current-password"
                            type="password"
                            autoComplete="current-password"
                            value={currentPassword}
                            onChange={(e) => {
                              setCurrentPassword(e.target.value);
                              setPasswordError(null);
                            }}
                            className="w-full bg-terminal-bg border border-outline-variant px-3 py-2 text-on-surface font-mono text-xs focus:border-primary focus:ring-1 focus:ring-primary outline-none rounded-xs"
                            placeholder="••••••••"
                            disabled={isChangingPassword}
                          />
                        </div>

                        <div>
                          <label htmlFor="profile-new-password" className="block font-mono text-[10px] uppercase text-on-surface-variant mb-1">
                            New Password
                          </label>
                          <input
                            id="profile-new-password"
                            type="password"
                            autoComplete="new-password"
                            value={newPassword}
                            onChange={(e) => {
                              setNewPassword(e.target.value);
                              setPasswordError(null);
                            }}
                            className="w-full bg-terminal-bg border border-outline-variant px-3 py-2 text-on-surface font-mono text-xs focus:border-primary focus:ring-1 focus:ring-primary outline-none rounded-xs"
                            placeholder="•••••••• (min 8 chars)"
                            disabled={isChangingPassword}
                          />
                        </div>

                        <div>
                          <label htmlFor="profile-confirm-password" className="block font-mono text-[10px] uppercase text-on-surface-variant mb-1">
                            Confirm New Password
                          </label>
                          <input
                            id="profile-confirm-password"
                            type="password"
                            autoComplete="new-password"
                            value={confirmPassword}
                            onChange={(e) => {
                              setConfirmPassword(e.target.value);
                              setPasswordError(null);
                            }}
                            className="w-full bg-terminal-bg border border-outline-variant px-3 py-2 text-on-surface font-mono text-xs focus:border-primary focus:ring-1 focus:ring-primary outline-none rounded-xs"
                            placeholder="••••••••"
                            disabled={isChangingPassword}
                          />
                        </div>

                        {passwordError && (
                          <p role="alert" className="font-mono text-[10px] text-error mt-1">{passwordError}</p>
                        )}
                      </div>

                      <button
                        type="submit"
                        disabled={isChangingPassword || !currentPassword || !newPassword || !confirmPassword}
                        className="h-9 px-4 border border-primary text-primary hover:bg-primary/10 font-mono text-xs uppercase font-bold tracking-wide rounded-sm btn-interactive disabled:opacity-40 disabled:pointer-events-none cursor-pointer flex items-center justify-center gap-1.5 self-start"
                      >
                        {isChangingPassword ? (
                          <>
                            <span className="material-symbols-outlined text-sm animate-spin">refresh</span>
                            UPDATING...
                          </>
                        ) : (
                          <>
                            <span className="material-symbols-outlined text-sm">key</span>
                            CHANGE PASSWORD
                          </>
                        )}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedPlayProject && (
        <PrototypeModal
          project={selectedPlayProject}
          onClose={() => setSelectedPlayProject(null)}
          onProjectUpdated={updateGameProject}
        />
      )}

      {/* Avatar Management Modal */}
      {showAvatarModal &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm"
            onClick={(e) => {
              if (e.target === e.currentTarget && !isUploadingAvatar) setShowAvatarModal(false);
            }}
          >
            <div
              className="w-full max-w-md bg-surface border-2 border-primary rounded-sm flex flex-col shadow-[0_0_30px_rgba(0,240,255,0.2)]"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="bg-terminal-header border-b border-primary/30 p-3 flex justify-between items-center">
                <div className="flex items-center gap-2 text-primary">
                  <span className="material-symbols-outlined text-sm">photo_camera</span>
                  <span className="font-mono text-sm tracking-widest font-bold uppercase">Profile Picture</span>
                </div>
                <button
                  onClick={() => !isUploadingAvatar && setShowAvatarModal(false)}
                  className="text-on-surface-variant hover:text-primary p-1 cursor-pointer"
                  disabled={isUploadingAvatar}
                >
                  <span className="material-symbols-outlined text-sm">close</span>
                </button>
              </div>

              <div className="p-6 bg-terminal-bg space-y-4">
                <div className="flex flex-col items-center gap-4">
                  <div className="w-28 h-28 rounded-sm border-2 border-primary/60 bg-surface-container-high flex items-center justify-center overflow-hidden glow-box-cyan">
                    {avatarPreview ? (
                      <img src={avatarPreview} alt="Preview" className="w-full h-full object-cover" />
                    ) : state.user?.avatar_url ? (
                      <img src={state.user.avatar_url} alt="Current Avatar" className="w-full h-full object-cover" />
                    ) : (
                      <span className="material-symbols-outlined text-primary text-[56px]">person</span>
                    )}
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="hidden"
                    onChange={handleFileSelect}
                  />

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="px-3.5 py-1.5 border border-primary/60 bg-primary/10 text-primary font-mono text-xs uppercase rounded-sm hover:bg-primary/20 cursor-pointer"
                      disabled={isUploadingAvatar}
                    >
                      Browse Image
                    </button>
                    {state.user?.avatar_url && (
                      <button
                        onClick={handleDeleteAvatar}
                        className="px-3.5 py-1.5 border border-error/50 text-error font-mono text-xs uppercase rounded-sm hover:bg-error/10 cursor-pointer"
                        disabled={isUploadingAvatar}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <p className="text-[11px] font-mono text-on-surface-variant text-center">
                    Supported: PNG, JPEG, WebP • Max Size: 2MB
                  </p>
                </div>

                {avatarError && (
                  <div className="p-2.5 bg-error/10 border border-error/40 text-error font-mono text-xs rounded-sm">
                    {avatarError}
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    onClick={() => setShowAvatarModal(false)}
                    className="px-4 py-2 border border-outline-variant font-mono text-xs uppercase text-on-surface-variant hover:text-on-surface cursor-pointer rounded-sm"
                    disabled={isUploadingAvatar}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleUploadAvatar}
                    disabled={!avatarFile || isUploadingAvatar}
                    className="px-4 py-2 bg-primary text-on-primary font-mono text-xs uppercase font-bold glow-cyan rounded-sm disabled:opacity-50 cursor-pointer"
                  >
                    {isUploadingAvatar ? 'Uploading...' : 'Save Avatar'}
                  </button>
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* Liked Games Modal */}
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
                  <div
                    key={sd.id}
                    onClick={() => {
                      setShowLikedGamesModal(false);
                      openSavedGameDetails(sd);
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setShowLikedGamesModal(false);
                        openSavedGameDetails(sd);
                      }
                    }}
                    className="flex items-center justify-between p-3 bg-surface border border-outline-variant hover:border-secondary/50 rounded-sm cursor-pointer group transition-colors focus:outline-none focus:ring-1 focus:ring-secondary"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-10 h-10 bg-secondary-container border border-secondary/40 rounded flex items-center justify-center shrink-0 overflow-hidden relative">
                        <SavedDiscoveryCover discovery={sd} className="w-full h-full object-cover" />
                      </div>
                      <div className="overflow-hidden">
                        <h4 className="font-mono text-xs text-primary font-bold group-hover:text-primary-bright truncate">{sd.title}</h4>
                        <p className="font-mono text-[10px] text-on-surface-variant truncate">{sd.genres.join(', ') || 'Game'}</p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSavedDiscovery(sd.id);
                      }}
                      className="text-error hover:underline font-mono text-xs cursor-pointer p-1 shrink-0"
                      aria-label={`Remove ${sd.title} from saved`}
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
}
