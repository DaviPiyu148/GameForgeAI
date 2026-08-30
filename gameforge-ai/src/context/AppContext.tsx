import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import type { ReactNode } from 'react';
import type {
  AppState,
  BuildParams,
  AppContextType,
  GameProject,
  LoginRequest,
  RegisterRequest,
} from '../types';
import { projectService } from '../services/projects';
import { buildService } from '../services/builds';
import { discoveryService } from '../services/discovery';
import { authService, authStorage, savedDiscoveriesService } from '../services/auth';
import { profileService } from '../services/profile';
import { pushToast } from '../services/toastBus';

const defaultBuildParams: BuildParams = {
  // Must match BuilderPage.tsx's <option> values and backend BuildParams schema defaults.
  engine: 'Top-Down Action',
  artDensity: 50,
  physics: 80,
  modules: ['Procedural Generation', 'Enhanced NPC Behavior'],
  scale: 'standard',
  world_mode: 'linear',
};

const defaultState: AppState = {
  user: null,
  authStatus: 'IDLE',
  isAuthModalOpen: false,
  authModalMode: 'login',
  authModalReason: undefined,
  postAuthAction: null,
  myGames: [],
  savedDiscoveries: [],
  isSavedDiscoveriesLoading: false,
  currentBuildParams: defaultBuildParams,
  currentPrompt: '',
  buildStatus: 'IDLE',
  compilerLogs: [],
  currentBuildId: null,
  activeProjectId: null,
  lastError: null,
  isSearching: false,
  discoveryResults: [],
  isProjectsLoading: false,
  projectsError: null,
  progress: null,
  preferences: null,
};

const DRAFT_STORAGE_KEY = 'gameforge_ai_drafts';

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<AppState>(() => {
    // Only restore editor drafts (prompt + build parameters) from localStorage.
    // User profile and saved discoveries are strictly backend-authoritative.
    let draftPrompt = '';
    let draftParams = defaultBuildParams;

    try {
      const stored = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.currentPrompt) draftPrompt = parsed.currentPrompt;
        if (parsed.currentBuildParams) draftParams = parsed.currentBuildParams;
      }
    } catch (e) {
      console.error('Failed to parse local drafts from localStorage', e);
    }

    return {
      ...defaultState,
      currentPrompt: draftPrompt,
      currentBuildParams: draftParams,
    };
  });

  const unsubscribeSseRef = useRef<(() => void) | null>(null);
  const authHydrationStartedRef = useRef(false);

  // 1. Backend Project Hydration
  const refreshProjects = useCallback(async () => {
    const token = authStorage.getToken();
    if (!token) {
      setState((s) => ({ ...s, myGames: [], isProjectsLoading: false }));
      return;
    }

    setState((s) => ({ ...s, isProjectsLoading: true, projectsError: null }));
    try {
      const projects = await projectService.getProjects();
      setState((s) => ({
        ...s,
        myGames: projects,
        isProjectsLoading: false,
      }));
    } catch (err) {
      console.warn('Failed to load projects from backend API', err);
      setState((s) => ({
        ...s,
        isProjectsLoading: false,
        projectsError: 'Could not load projects from backend.',
      }));
    }
  }, []);

  // 2. Backend Saved Discoveries Hydration
  const refreshSavedDiscoveries = useCallback(async () => {
    const token = authStorage.getToken();
    if (!token) {
      setState((s) => ({ ...s, savedDiscoveries: [], isSavedDiscoveriesLoading: false }));
      return;
    }

    setState((s) => ({ ...s, isSavedDiscoveriesLoading: true }));
    try {
      const discoveries = await savedDiscoveriesService.getSaved();
      setState((s) => ({
        ...s,
        savedDiscoveries: discoveries,
        isSavedDiscoveriesLoading: false,
      }));
    } catch (err) {
      console.warn('Failed to load saved discoveries from backend API', err);
      setState((s) => ({
        ...s,
        isSavedDiscoveriesLoading: false,
      }));
    }
  }, []);

  // 2B. Backend Progress & Level Hydration
  const refreshProgress = useCallback(async () => {
    const token = authStorage.getToken();
    if (!token) {
      setState((s) => ({ ...s, progress: null }));
      return;
    }
    try {
      const progress = await profileService.getProgress();
      setState((s) => {
        // Diff against the previously-known progress snapshot (if any) to raise
        // celebratory toasts for XP gain / level up / newly unlocked milestones.
        // Purely a UI side-effect — does not alter the fetched data or any state shape.
        const prev = s.progress;
        if (prev) {
          const xpGained = progress.total_xp - prev.total_xp;
          if (progress.current_level > prev.current_level) {
            pushToast({
              variant: 'levelup',
              title: `LEVEL UP → ${progress.current_level}`,
              description: progress.creator_title,
            });
          } else if (xpGained > 0) {
            pushToast({ variant: 'xp', title: `+${xpGained} XP` });
          }

          if (progress.unlocked_milestone_count > prev.unlocked_milestone_count) {
            const newlyUnlocked = progress.milestones.find(
              (m) => m.is_unlocked && !prev.milestones.some((pm) => pm.milestone_key === m.milestone_key && pm.is_unlocked)
            );
            pushToast({
              variant: 'milestone',
              title: 'NEW MILESTONE',
              description: newlyUnlocked?.title,
            });
          }
        }

        return {
          ...s,
          progress,
          user: s.user ? { ...s.user, level: progress.current_level } : null,
        };
      });
    } catch (err) {
      console.warn('Failed to load progress from backend API', err);
    }
  }, []);

  // 2C. Backend Genre Preferences Hydration
  const refreshPreferences = useCallback(async () => {
    const token = authStorage.getToken();
    if (!token) {
      setState((s) => ({ ...s, preferences: null }));
      return;
    }
    try {
      const preferences = await profileService.getPreferences();
      setState((s) => ({ ...s, preferences }));
    } catch (err) {
      console.warn('Failed to load preferences from backend API', err);
    }
  }, []);

  // 2D. Profile Picture Upload & Delete
  const uploadAvatar = useCallback(async (file: File): Promise<string> => {
    const res = await profileService.uploadAvatar(file);
    setState((s) => ({
      ...s,
      user: s.user ? { ...s.user, avatar_url: res.avatar_url } : null,
    }));
    return res.avatar_url;
  }, []);

  const deleteAvatar = useCallback(async (): Promise<void> => {
    await profileService.deleteAvatar();
    setState((s) => ({
      ...s,
      user: s.user ? { ...s.user, avatar_url: null } : null,
    }));
  }, []);

  // 3. Initial Auth Hydration from /api/auth/me
  useEffect(() => {
    const initAuth = async () => {
      const token = authStorage.getToken();
      if (!token) {
        setState((s) => ({ ...s, authStatus: 'UNAUTHENTICATED', user: null }));
        return;
      }

      if (authHydrationStartedRef.current) return;
      authHydrationStartedRef.current = true;

      setState((s) => ({ ...s, authStatus: 'LOADING' }));
      try {
        const user = await authService.getMe();
        setState((s) => ({
          ...s,
          user,
          authStatus: 'AUTHENTICATED',
        }));
        // Hydrate backend data
        await Promise.all([
          refreshProjects(),
          refreshSavedDiscoveries(),
          refreshProgress(),
          refreshPreferences(),
        ]);
      } catch (err) {
        console.warn('Auth token invalid or expired; resetting session', err);
        authStorage.clearToken();
        authHydrationStartedRef.current = false;
        setState((s) => ({
          ...s,
          user: null,
          authStatus: 'UNAUTHENTICATED',
          myGames: [],
          savedDiscoveries: [],
          progress: null,
          preferences: null,
        }));
      }
    };

    initAuth();
  }, [refreshProjects, refreshSavedDiscoveries, refreshProgress, refreshPreferences]);

  // 4. Persist ONLY local drafts (Prompt, Build Params) - NEVER user or saved data
  useEffect(() => {
    try {
      const localDraft = {
        currentBuildParams: state.currentBuildParams,
        currentPrompt: state.currentPrompt,
      };
      localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(localDraft));
    } catch (e) {
      console.error('Failed to persist draft state to localStorage', e);
    }
  }, [state.currentBuildParams, state.currentPrompt]);

  // Cleanup SSE and global auth-expired listener on unmount
  useEffect(() => {
    const handleAuthExpired = () => {
      authStorage.clearToken();
      setState((s) => ({
        ...s,
        user: null,
        authStatus: 'UNAUTHENTICATED',
        myGames: [],
        savedDiscoveries: [],
      }));
    };

    window.addEventListener('gameforge:auth-expired', handleAuthExpired);

    return () => {
      window.removeEventListener('gameforge:auth-expired', handleAuthExpired);
      if (unsubscribeSseRef.current) {
        unsubscribeSseRef.current();
        unsubscribeSseRef.current = null;
      }
    };
  }, []);

  // Auth Modal Controls
  const openAuthModal = (
    mode: 'login' | 'register' = 'login',
    reason?: string,
    onAuthenticated?: () => void
  ) => {
    setState((s) => ({
      ...s,
      isAuthModalOpen: true,
      authModalMode: mode,
      authModalReason: reason,
      postAuthAction: onAuthenticated || null,
    }));
  };

  const closeAuthModal = () => {
    setState((s) => ({
      ...s,
      isAuthModalOpen: false,
      authModalReason: undefined,
      postAuthAction: null,
    }));
  };

  // Login Handler
  const login = async (data: LoginRequest) => {
    const res = await authService.login(data);
    const postAction = state.postAuthAction;
    authHydrationStartedRef.current = true;
    setState((s) => ({
      ...s,
      user: res.user,
      authStatus: 'AUTHENTICATED',
      isAuthModalOpen: false,
      authModalReason: undefined,
      postAuthAction: null,
    }));
    await Promise.all([
      refreshProjects(),
      refreshSavedDiscoveries(),
      refreshProgress(),
      refreshPreferences(),
    ]);
    if (postAction) {
      postAction();
    }
  };

  // Register Handler
  const register = async (data: RegisterRequest) => {
    const res = await authService.register(data);
    const postAction = state.postAuthAction;
    authHydrationStartedRef.current = true;
    setState((s) => ({
      ...s,
      user: res.user,
      authStatus: 'AUTHENTICATED',
      isAuthModalOpen: false,
      authModalReason: undefined,
      postAuthAction: null,
    }));
    await Promise.all([
      refreshProjects(),
      refreshSavedDiscoveries(),
      refreshProgress(),
      refreshPreferences(),
    ]);
    if (postAction) {
      postAction();
    }
  };

  // Logout Handler
  const logout = () => {
    authService.logout();
    authHydrationStartedRef.current = false;
    setState((s) => ({
      ...s,
      user: null,
      authStatus: 'UNAUTHENTICATED',
      myGames: [],
      savedDiscoveries: [],
      progress: null,
      preferences: null,
      // Also clear build/error state: without this, a previous session's build
      // error/logs (e.g. state.lastError, state.compilerLogs) remained fully visible
      // via #/status/error to whoever uses the app next on the same device, since
      // ErrorStatusPage's own guard only checks buildStatus, not auth.
      buildStatus: 'IDLE',
      compilerLogs: [],
      currentBuildId: null,
      activeProjectId: null,
      lastError: null,
    }));
  };

  // Saved Discoveries Actions
  const saveDiscovery = async (steamAppId: string) => {
    if (state.authStatus !== 'AUTHENTICATED' || !state.user) {
      openAuthModal('login', 'Please log in to save game discoveries to your collection.');
      return;
    }
    try {
      const saved = await savedDiscoveriesService.saveDiscovery(steamAppId);
      setState((s) => ({
        ...s,
        savedDiscoveries: [saved, ...s.savedDiscoveries.filter((d) => d.id !== saved.id)],
      }));
      pushToast({ variant: 'success', title: 'GAME SAVED', description: saved.title });
    } catch (err) {
      // Prevents an unhandled promise rejection when a caller (e.g. HomePage's Save
      // button) invokes this without awaiting/catching. A failed save (expired token,
      // 409 already-saved, rate limit, network error) is silently retryable rather
      // than crashing the click handler.
      console.warn('Failed to save discovery:', err);
    }
  };

  const removeSavedDiscovery = async (id: string) => {
    await savedDiscoveriesService.deleteSaved(id);
    setState((s) => ({
      ...s,
      savedDiscoveries: s.savedDiscoveries.filter((d) => d.id !== id),
    }));
  };

  const setPrompt = (prompt: string) => setState((s) => ({ ...s, currentPrompt: prompt }));
  const updateBuildParams = (params: Partial<BuildParams>) =>
    setState((s) => ({ ...s, currentBuildParams: { ...s.currentBuildParams, ...params } }));
  const setBuildStatus = (status: AppState['buildStatus']) => setState((s) => ({ ...s, buildStatus: status }));
  const addGameProject = (project: GameProject) =>
    setState((s) => ({ ...s, myGames: [project, ...s.myGames] }));
  // Updates an existing project already in myGames in place (e.g. after PrototypeModal
  // applies an AI improvement and bumps its version) so every view reading state.myGames
  // (Dashboard cards, version counts, a later reopened PrototypeModal) reflects the
  // change immediately instead of only the modal's own local component state.
  const updateGameProject = (project: GameProject) =>
    setState((s) => ({
      ...s,
      myGames: s.myGames.map((g) => (g.id === project.id ? project : g)),
    }));
  const clearCompilerLogs = () => setState((s) => ({ ...s, compilerLogs: [] }));

  const clearDiscoveryResults = () => setState((s) => ({ ...s, discoveryResults: [] }));

  // Sprint A — Project Management
  const deleteProject = async (id: string): Promise<void> => {
    await projectService.deleteProject(id);
    setState((s) => ({
      ...s,
      myGames: s.myGames.filter((g) => g.id !== id),
    }));
    pushToast({ variant: 'success', title: 'PROJECT DELETED', description: 'The project has been permanently removed.' });
  };

  const duplicateProject = async (id: string): Promise<void> => {
    const copy = await projectService.duplicateProject(id);
    setState((s) => ({
      ...s,
      myGames: [copy, ...s.myGames],
    }));
    pushToast({ variant: 'success', title: 'PROJECT DUPLICATED', description: `'${copy.title}' created.` });
  };

  // 5. Real Discovery Search Flow (Public, zero auth requirement)
  const searchDiscovery = async (promptText: string, navigate: (path: string) => void) => {
    const trimmed = promptText.trim();
    if (!trimmed) {
      navigate('/build');
      return;
    }

    setPrompt(trimmed);
    setState((s) => ({ ...s, isSearching: true, discoveryResults: [] }));

    try {
      // Request up to 24 candidates from backend discovery index
      const response = await discoveryService.searchGames(trimmed, 24);
      setState((s) => ({
        ...s,
        isSearching: false,
        discoveryResults: response.results || [],
      }));

      if (response.no_strong_match || !response.results || response.results.length === 0) {
        navigate('/discover/no-matches');
      } else {
        // Remain on Home/Discover page (or navigate to / if initiated elsewhere)
        navigate('/');
      }
    } catch (err) {
      console.warn('Discovery search error, navigating to no-matches fallback', err);
      setState((s) => ({ ...s, isSearching: false }));
      navigate('/discover/no-matches');
    }
  };

  // 6. Real Build Pipeline Execution (Auth Gated)
  const compileProject = async (navigate: (path: string) => void) => {
    if (state.authStatus !== 'AUTHENTICATED' || !state.user) {
      openAuthModal('login', 'Please log in to compile and build your game prototype.');
      return;
    }

    if (state.buildStatus === 'COMPILING') return;

    // Cleanup previous SSE subscription if any
    if (unsubscribeSseRef.current) {
      unsubscribeSseRef.current();
      unsubscribeSseRef.current = null;
    }

    setState((s) => ({
      ...s,
      buildStatus: 'COMPILING',
      currentBuildId: null,
      lastError: null,
      compilerLogs: [
        '[SYS] Initializing GameForge build pipeline...',
        '[SYS] Submitting build parameters to FastAPI service...',
      ],
    }));

    try {
      const buildRes = await buildService.createBuild(
        state.currentPrompt,
        state.currentBuildParams
      );

      const buildId = buildRes.build_id;
      setState((s) => ({
        ...s,
        currentBuildId: buildId,
        compilerLogs: [...s.compilerLogs, `[SYS] Build job queued (ID: ${buildId.substring(0, 8)}...)`],
      }));

      const seenLogSequences = new Set<number>();

      // Subscribe to real-time Server-Sent Events
      const unsubscribe = buildService.subscribeBuildEvents(buildId, {
        onLog: (log) => {
          if (!seenLogSequences.has(log.sequence)) {
            seenLogSequences.add(log.sequence);
            setState((s) => ({
              ...s,
              compilerLogs: [...s.compilerLogs, log.message],
            }));
          }
        },
        onStatus: async (statusData) => {
          if (statusData.status === 'SUCCESS') {
            const projectId = statusData.project_id;
            if (projectId) {
              try {
                // Fetch the authoritative Project record with full Game DSL and runtime metadata
                const newProject = await projectService.getProject(projectId);
                setState((s) => ({
                  ...s,
                  buildStatus: 'SUCCESS',
                  activeProjectId: projectId,
                  myGames: [newProject, ...s.myGames.filter((g) => g.id !== projectId)],
                }));
              } catch (fetchErr) {
                console.warn('Failed to fetch created project metadata', fetchErr);
                setState((s) => ({
                  ...s,
                  buildStatus: 'SUCCESS',
                  activeProjectId: projectId,
                }));
              }
            } else {
              setState((s) => ({ ...s, buildStatus: 'SUCCESS' }));
            }
            await Promise.all([
              refreshProjects(),
              refreshSavedDiscoveries(),
              refreshProgress(),
              refreshPreferences(),
            ]);
            pushToast({ variant: 'success', title: 'BUILD COMPLETE', description: 'Prototype ready to play.' });
            navigate('/status/success');
          } else if (statusData.status === 'ERROR') {
            setState((s) => ({
              ...s,
              buildStatus: 'ERROR',
              lastError: {
                code: statusData.error_code || 'BUILD_FAILED',
                message: statusData.error_message || 'Compilation failed.',
              },
            }));
            navigate('/status/error');
          } else if (statusData.status === 'CANCELLED') {
            setState((s) => ({
              ...s,
              buildStatus: 'IDLE',
              currentBuildId: null,
              compilerLogs: [...s.compilerLogs, '[SYS] BUILD CANCELLED BY USER'],
            }));
          }
        },
        onError: (sseErr) => {
          console.warn('SSE stream error event received', sseErr);
        },
      });

      unsubscribeSseRef.current = unsubscribe;
    } catch (err) {
      console.error('Failed to submit build job to backend', err);
      const message = err instanceof Error ? err.message : 'Failed to connect to build service.';
      setState((s) => ({
        ...s,
        buildStatus: 'ERROR',
        lastError: {
          code: 'CONNECTION_FAILED',
          message,
        },
        compilerLogs: [...s.compilerLogs, `> FATAL_EXCEPTION: ${message}`],
      }));
      navigate('/status/error');
    }
  };

  // 7. Cancel Active Build
  const cancelCurrentBuild = async () => {
    if (state.buildStatus !== 'COMPILING' || !state.currentBuildId) return;

    if (unsubscribeSseRef.current) {
      unsubscribeSseRef.current();
      unsubscribeSseRef.current = null;
    }

    const buildId = state.currentBuildId;
    try {
      await buildService.cancelBuild(buildId);
    } catch (err) {
      console.warn('Failed to send build cancellation to backend', err);
    }

    setState((s) => ({
      ...s,
      buildStatus: 'IDLE',
      currentBuildId: null,
      compilerLogs: [...s.compilerLogs, '[SYS] BUILD CANCELLED BY USER'],
    }));
  };

  // 8. Retry Build
  const retryBuild = async (navigate: (path: string) => void) => {
    await compileProject(navigate);
  };

  return (
    <AppContext.Provider
      value={{
        state,
        setPrompt,
        updateBuildParams,
        setBuildStatus,
        addGameProject,
        updateGameProject,
        setState,
        compileProject,
        cancelCurrentBuild,
        retryBuild,
        searchDiscovery,
        refreshProjects,
        clearCompilerLogs,
        openAuthModal,
        closeAuthModal,
        login,
        register,
        logout,
        saveDiscovery,
        removeSavedDiscovery,
        refreshSavedDiscoveries,
        clearDiscoveryResults,
        refreshProgress,
        refreshPreferences,
        uploadAvatar,
        deleteAvatar,
        deleteProject,
        duplicateProject,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
