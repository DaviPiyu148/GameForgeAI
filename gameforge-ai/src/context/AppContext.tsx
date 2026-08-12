import { createContext, useContext, useState, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import type { AppState, BuildParams, AppContextType, GameProject, RecommendationMatch } from '../types';
import { recommendGames, buildProject } from '../services/api';

const defaultState: AppState = {
  currentUser: {
    id: 'user_1',
    username: 'Gamer_X',
    level: 42,
    avatarPlaceholder: 'mock_avatar_url'
  },
  myGames: [
    {
      id: 'mock_1',
      title: 'Neon Swarm',
      genre: '2D Survival',
      status: 'PLAYABLE',
      lastModified: 'Today, 14:32',
      parameters: { engine: 'Godot 4.0 Setup', artDensity: 20, physics: 50, modules: [] },
      prompt: 'A cyberpunk 2D survival game'
    },
    {
      id: 'mock_2',
      title: 'Void Drift',
      genre: 'Racing',
      status: 'PLAYABLE',
      lastModified: 'Yesterday',
      parameters: { engine: 'Unreal Engine 5 Core', artDensity: 80, physics: 100, modules: [] },
      prompt: 'A futuristic racing game'
    }
  ],
  savedDiscoveries: [
    { id: 'sd_1', matchPercentage: 95, savedDate: 'Oct 12', title: 'CASTLE RUNNER', author: '@DevZero', icon: 'castle', themeClass: 'secondary' },
    { id: 'sd_2', matchPercentage: 88, savedDate: 'Oct 10', title: 'VECTOR STRIKE', author: '@ArcadeAI', icon: 'rocket_launch', themeClass: 'primary' },
    { id: 'sd_3', matchPercentage: 72, savedDate: 'Oct 5', title: 'ECHO WILDS', author: '@GreenByte', icon: 'forest', themeClass: 'tertiary' },
    { id: 'sd_4', matchPercentage: 81, savedDate: 'Oct 3', title: 'PIXEL SORCERY', author: '@WizardAI', icon: 'auto_fix_high', themeClass: 'primary' },
  ],
  currentBuildParams: {
    engine: 'Unreal Engine 5 Core',
    artDensity: 50,
    physics: 80,
    modules: ['Procedural Gen', 'Advanced NPC AI']
  },
  currentPrompt: '',
  buildStatus: 'IDLE',
  compilerLogs: [],
  recommendations: []
};

const STORAGE_KEY = 'gameforge_ai_state';

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<AppState>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        return {
          ...defaultState,
          ...parsed,
          buildStatus: 'IDLE',
          compilerLogs: [],
          recommendations: []
        };
      }
    } catch (e) {
      console.error('Failed to parse state from localStorage', e);
    }
    return defaultState;
  });

  const timerRef = useRef<number | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    try {
      const stateToPersist = {
        ...state,
        buildStatus: 'IDLE',
        compilerLogs: [],
        recommendations: []
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToPersist));
    } catch (e) {
      console.error('Failed to persist state to localStorage', e);
    }
  }, [state.myGames, state.savedDiscoveries, state.currentBuildParams, state.currentPrompt]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, []);

  const setPrompt = (prompt: string) => setState(s => ({ ...s, currentPrompt: prompt }));
  const updateBuildParams = (params: Partial<BuildParams>) => setState(s => ({ ...s, currentBuildParams: { ...s.currentBuildParams, ...params } }));
  const setBuildStatus = (status: AppState['buildStatus']) => setState(s => ({ ...s, buildStatus: status }));
  const addGameProject = (project: GameProject) => setState(s => ({ ...s, myGames: [project, ...s.myGames] }));
  const clearCompilerLogs = () => setState(s => ({ ...s, compilerLogs: [] }));

  const fetchRecommendations = async (prompt: string): Promise<RecommendationMatch[]> => {
    try {
      const response = await recommendGames(prompt);
      const matches = response.matches || [];
      setState(s => ({ ...s, recommendations: matches }));
      return matches;
    } catch (err) {
      console.warn('Backend recommendation request failed or offline:', err);
      setState(s => ({ ...s, recommendations: [] }));
      return [];
    }
  };

  const compileProject = (navigate: (path: string) => void) => {
    if (state.buildStatus === 'COMPILING') return;

    if (timerRef.current) window.clearTimeout(timerRef.current);
    if (intervalRef.current) window.clearInterval(intervalRef.current);

    const activePrompt = state.currentPrompt;
    const activeParams = state.currentBuildParams;

    setState(s => ({
      ...s,
      buildStatus: 'COMPILING',
      compilerLogs: [
        '[SYS] Initializing build pipeline...', 
        '[SYS] Analyzing prompt syntax...',
        ...activeParams.modules.map(m => `[MOD] Linking module: ${m}`)
      ]
    }));

    // Trigger backend build request asynchronously
    const apiBuildPromise = buildProject(activePrompt, activeParams).catch(err => {
      return { _isError: true, error: err };
    });

    let step = 0;
    intervalRef.current = window.setInterval(() => {
      step++;
      if (step === 1) {
        setState(s => ({ ...s, compilerLogs: [...s.compilerLogs, '[SYS] Generating world geometries...'] }));
      } else if (step === 2) {
        setState(s => ({ ...s, compilerLogs: [...s.compilerLogs, '[SYS] Running physics simulation pass...'] }));
      }
    }, 800);

    timerRef.current = window.setTimeout(async () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);

      const apiResult = await apiBuildPromise;
      const localHasError = /\bERROR\b/i.test(activePrompt);

      let isError = localHasError;
      let newProject: GameProject | null = null;

      if (apiResult && '_isError' in apiResult && apiResult._isError) {
        // Backend returned error (e.g. status 400 for ERROR) or network failure
        isError = true;
      } else if (apiResult && !('_isError' in apiResult) && apiResult.id) {
        isError = false;
        newProject = {
          id: apiResult.id,
          title: apiResult.title || activePrompt.substring(0, 40).trim() || 'UNTITLED PROJECT',
          genre: apiResult.genre || 'Generated Concept',
          status: 'PLAYABLE',
          lastModified: apiResult.lastModified || 'Just now',
          parameters: apiResult.parameters || activeParams,
          prompt: apiResult.prompt || activePrompt
        };
      }

      // Fallback if backend was unreachable or returned offline fallback
      if (!isError && !newProject) {
        newProject = {
          id: `proj_${Date.now().toString(16)}`,
          title: activePrompt.substring(0, 40).trim() || 'UNTITLED PROJECT',
          genre: 'Generated Concept',
          status: 'PLAYABLE',
          lastModified: 'Just now',
          parameters: activeParams,
          prompt: activePrompt
        };
      }

      setState(s => {
        if (isError) {
          setTimeout(() => navigate('/status/error'), 0);
          return {
            ...s,
            buildStatus: 'ERROR',
            compilerLogs: [...s.compilerLogs, '> FATAL_EXCEPTION: BUILD_FAILED', 'Process terminated unexpectedly.']
          };
        } else if (newProject) {
          setTimeout(() => navigate('/status/success'), 0);
          return {
            ...s,
            buildStatus: 'SUCCESS',
            myGames: [newProject, ...s.myGames],
            compilerLogs: [...s.compilerLogs, '[SYS] Compilation successful. Build ready.']
          };
        }
        return s;
      });
    }, 3000);
  };

  return (
    <AppContext.Provider
      value={{
        state,
        setPrompt,
        updateBuildParams,
        setBuildStatus,
        addGameProject,
        setState,
        compileProject,
        clearCompilerLogs,
        fetchRecommendations
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
