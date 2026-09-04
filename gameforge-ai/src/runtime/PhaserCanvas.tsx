import React, { useEffect, useRef, useState, useCallback } from 'react';
import Phaser from 'phaser';
import type { GameDSL, GameState, PlaytestSummary } from './types';
import { GameScene } from './GameScene';

interface PhaserCanvasProps {
  gameDsl: GameDSL;
  seed?: number;
  onClose?: () => void;
  onPlaytestComplete?: (summary: PlaytestSummary) => void;
  isPausedExternal?: boolean;
}

export const PhaserCanvas: React.FC<PhaserCanvasProps> = ({
  gameDsl,
  seed,
  onClose,
  onPlaytestComplete,
  isPausedExternal = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const [gameState, setGameState] = useState<GameState>('PLAYING');
  const onPlaytestCompleteRef = useRef(onPlaytestComplete);

  // Sync external pause (e.g. when Remix drawer opens)
  useEffect(() => {
    if (gameRef.current) {
      const scene = gameRef.current.scene.getScene('GameScene');
      if (scene) {
        if (isPausedExternal) {
          scene.scene.pause();
          setGameState('PAUSED');
        } else {
          setGameState((prev) => {
            if (prev === 'PAUSED') {
              scene.scene.resume();
              return 'PLAYING';
            }
            return prev;
          });
        }
      }
    }
  }, [isPausedExternal]);

  useEffect(() => {
    onPlaytestCompleteRef.current = onPlaytestComplete;
  }, [onPlaytestComplete]);

  const handleRestart = useCallback(() => {
    if (gameRef.current) {
      gameRef.current.scene.stop('GameScene');
      gameRef.current.scene.start('GameScene', {
        dsl: gameDsl,
        seed: (seed ?? 18492031) + Math.floor(Math.random() * 1000),
        onStateChange: (state: GameState) => {
          setGameState(state);
        },
        onPlaytestComplete: (summary: PlaytestSummary) => {
          if (onPlaytestCompleteRef.current) {
            onPlaytestCompleteRef.current(summary);
          }
        },
      });
      setGameState('PLAYING');
      // Re-focus canvas on restart
      setTimeout(() => {
        containerRef.current?.querySelector('canvas')?.focus();
      }, 50);
    }
  }, [gameDsl, seed]);

  const handleTogglePause = useCallback(() => {
    if (gameRef.current) {
      const scene = gameRef.current.scene.getScene('GameScene');
      if (scene) {
        if (gameState === 'PAUSED') {
          scene.scene.resume();
          setGameState('PLAYING');
        } else {
          scene.scene.pause();
          setGameState('PAUSED');
        }
      }
    }
  }, [gameState]);

  // Keyboard shortcut listener for P (Pause/Resume) and R (Restart)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = (document.activeElement as HTMLElement)?.tagName;
      if (['INPUT', 'TEXTAREA'].includes(activeTag)) return;

      if (e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        handleTogglePause();
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        handleRestart();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleTogglePause, handleRestart]);

  useEffect(() => {
    if (!containerRef.current) return;

    if (gameRef.current) {
      gameRef.current.destroy(true);
      gameRef.current = null;
    }

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      parent: containerRef.current,
      width: Math.min(800, gameDsl.world.width),
      height: Math.min(500, gameDsl.world.height),
      backgroundColor: gameDsl.world.background_color || '#0a0b12',
      physics: {
        default: 'arcade',
        arcade: {
          gravity: {
            x: 0,
            y: gameDsl.metadata.archetype === 'platformer' ? gameDsl.world.gravity || 800 : 0,
          },
          debug: false,
        },
      },
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
      input: {
        keyboard: {
          target: window,
        },
      },
      scene: [GameScene],
    };

    const game = new Phaser.Game(config);
    gameRef.current = game;

    game.scene.start('GameScene', {
      dsl: gameDsl,
      seed: seed ?? 18492031,
      onStateChange: (state: GameState) => {
        setGameState(state);
      },
      onPlaytestComplete: (summary: PlaytestSummary) => {
        if (onPlaytestCompleteRef.current) {
          onPlaytestCompleteRef.current(summary);
        }
      },
    });

    // Ensure game canvas is focusable and immediately focused
    const focusTimer = setTimeout(() => {
      const canvas = containerRef.current?.querySelector('canvas');
      if (canvas) {
        canvas.setAttribute('tabindex', '0');
        canvas.focus();
      }
    }, 60);

    return () => {
      clearTimeout(focusTimer);
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
  }, [gameDsl, seed]);

  const getArchetypeLabel = () => {
    switch (gameDsl.metadata.archetype) {
      case 'survival':
        return 'Top-Down Survival (Waves & Collect)';
      case 'shooter':
        return 'Top-Down Arena Shooter (Combat & Waves)';
      case 'platformer':
        return '2D Platformer (Jump, Dash & Goal)';
      case 'collector':
        return 'Data Collector Prototype';
      default:
        return '2D Action Prototype';
    }
  };

  return (
    <div className="flex flex-col w-full h-full bg-[#05060a] rounded-lg overflow-hidden border border-primary/40">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-terminal-header border-b border-primary/30">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary text-xl animate-pulse">videogame_asset</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold text-on-surface">{gameDsl.metadata.title}</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/30 uppercase">
                {gameDsl.metadata.archetype}
              </span>
            </div>
            <p className="text-[11px] font-mono text-on-surface-variant">{getArchetypeLabel()}</p>
          </div>
        </div>

        {/* Runtime Control Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleTogglePause}
            className="px-3 py-1 text-xs font-mono rounded bg-surface border border-primary/40 text-primary hover:bg-primary/20 transition-colors flex items-center gap-1.5 focus:ring-1 focus:ring-primary cursor-pointer"
            title="Pause / Resume Game [P]"
          >
            <span className="material-symbols-outlined text-sm">{gameState === 'PAUSED' ? 'play_arrow' : 'pause'}</span>
            <span>{gameState === 'PAUSED' ? 'RESUME [P]' : 'PAUSE [P]'}</span>
          </button>
          <button
            onClick={handleRestart}
            className="px-3 py-1 text-xs font-mono rounded bg-surface border border-secondary/40 text-secondary hover:bg-secondary/20 transition-colors flex items-center gap-1.5 focus:ring-1 focus:ring-secondary cursor-pointer"
            title="Restart Game [R]"
          >
            <span className="material-symbols-outlined text-sm">replay</span>
            <span>RESTART [R]</span>
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded text-on-surface-variant hover:text-error hover:bg-error/10 transition-colors ml-2 focus:ring-1 focus:ring-error cursor-pointer"
              aria-label="Close prototype"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          )}
        </div>
      </div>

      {/* Phaser Canvas Viewport */}
      <div 
        className="relative flex-1 w-full min-h-[420px] max-h-[500px] flex items-center justify-center bg-[#070810] overflow-hidden cursor-crosshair focus:outline-none focus:ring-1 focus:ring-primary/40"
        tabIndex={0}
        onClick={() => {
          containerRef.current?.querySelector('canvas')?.focus();
        }}
      >
        <div ref={containerRef} className="w-full h-full flex items-center justify-center" />
        {gameState === 'PAUSED' && (
          <div className="absolute inset-0 z-10 bg-background/75 backdrop-blur-xs flex flex-col items-center justify-center gap-2 pointer-events-none animate-fade-in">
            <span className="font-mono text-xs sm:text-sm font-bold text-secondary uppercase tracking-widest bg-surface/90 border border-secondary/50 px-4 py-2 rounded shadow-lg flex items-center gap-2">
              <span className="material-symbols-outlined text-sm">pause_circle</span>
              <span>GAMEPLAY PAUSED {isPausedExternal ? '// REMIX ACTIVE' : '// [P]'}</span>
            </span>
            <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-wider">
              {isPausedExternal ? 'Close or apply remix to resume playing' : 'Press P or click Resume to continue'}
            </span>
          </div>
        )}
      </div>

      {/* Bottom Controls / Status Guide */}
      <div className="px-4 py-2 bg-terminal-header border-t border-primary/20 flex items-center justify-between text-xs font-mono text-on-surface-variant">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="flex items-center gap-1 text-primary">
            <span className="font-bold text-white bg-primary/20 px-1.5 py-0.5 rounded border border-primary/40">WASD / ARROWS</span> Move
          </span>
          <span className="flex items-center gap-1 text-secondary">
            <span className="font-bold text-white bg-secondary/20 px-1.5 py-0.5 rounded border border-secondary/40">SPACE / SHIFT</span> Dash
          </span>
          <span className="flex items-center gap-1 text-amber-400">
            <span className="font-bold text-white bg-amber-400/20 px-1.5 py-0.5 rounded border border-amber-400/40">CLICK / F</span> Shoot
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-primary/70">Phaser 3.88.2</span>
          <span className="text-on-surface-variant/40">•</span>
          <span className="text-secondary/70">V2 Dynamic Runtime</span>
        </div>
      </div>
    </div>
  );
};
