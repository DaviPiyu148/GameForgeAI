export type WaveState = 'IDLE' | 'SPAWNING' | 'ACTIVE' | 'COMPLETED';

export interface WaveSpawnConfig {
  waveNumber: number;
  enemyCount: number;
  scaleBudgetMultiplier?: number;
}

export class WaveController {
  private currentWave = 0;
  private maxWaves: number;
  private state: WaveState = 'IDLE';
  private isTerminal = false;
  private isNotifying = false;
  private onWaveStartNotification?: (waveNum: number) => void;
  private onWaveSpawnEnemies?: (config: WaveSpawnConfig) => void;
  private onAllWavesCompleted?: () => void;

  constructor(
    maxWaves: number = 1,
    callbacks?: {
      onWaveStartNotification?: (waveNum: number) => void;
      onWaveSpawnEnemies?: (config: WaveSpawnConfig) => void;
      onAllWavesCompleted?: () => void;
    }
  ) {
    this.maxWaves = Math.max(1, maxWaves);
    this.onWaveStartNotification = callbacks?.onWaveStartNotification;
    this.onWaveSpawnEnemies = callbacks?.onWaveSpawnEnemies;
    this.onAllWavesCompleted = callbacks?.onAllWavesCompleted;
  }

  public getCurrentWave(): number {
    return this.currentWave;
  }

  public getMaxWaves(): number {
    return this.maxWaves;
  }

  public getState(): WaveState {
    return this.state;
  }

  public isCompleted(): boolean {
    return this.state === 'COMPLETED';
  }

  public setTerminal(isTerminal: boolean): void {
    this.isTerminal = isTerminal;
  }

  /**
   * Safe entry point to start the first wave upon scene creation without recursion.
   */
  public startInitialWave(): boolean {
    if (this.currentWave > 0 || this.isTerminal) return false;
    return this.advanceWave();
  }

  /**
   * Request advancing to the next wave.
   * Guarded against:
   * 1. Already spawning or notifying
   * 2. Exceeding max waves
   * 3. Terminal game states (WON, LOST)
   * 4. Recursive re-entry during on_wave_start notification
   */
  public requestNextWave(): boolean {
    if (this.isTerminal || this.isNotifying || this.state === 'SPAWNING' || this.state === 'COMPLETED') {
      return false;
    }

    if (this.currentWave >= this.maxWaves) {
      this.state = 'COMPLETED';
      if (this.onAllWavesCompleted) {
        this.onAllWavesCompleted();
      }
      return false;
    }

    return this.advanceWave();
  }

  private advanceWave(): boolean {
    if (this.isTerminal || this.isNotifying) return false;

    this.currentWave += 1;
    this.state = 'SPAWNING';

    // 1. Spawn enemy entities for this wave
    if (this.onWaveSpawnEnemies) {
      this.onWaveSpawnEnemies({
        waveNumber: this.currentWave,
        enemyCount: this.currentWave * 2,
      });
    }

    // 2. Emit on_wave_start notification with notification re-entrancy lock
    this.isNotifying = true;
    try {
      if (this.onWaveStartNotification) {
        this.onWaveStartNotification(this.currentWave);
      }
    } finally {
      this.isNotifying = false;
      this.state = 'ACTIVE';
    }

    return true;
  }

  /**
   * Notify that all wave enemies have been defeated.
   */
  public onWaveEnemiesCleared(): { shouldAdvance: boolean; isVictory: boolean } {
    if (this.isTerminal) return { shouldAdvance: false, isVictory: false };

    if (this.currentWave >= this.maxWaves) {
      this.state = 'COMPLETED';
      if (this.onAllWavesCompleted) {
        this.onAllWavesCompleted();
      }
      return { shouldAdvance: false, isVictory: true };
    }

    return { shouldAdvance: true, isVictory: false };
  }

  public reset(maxWaves?: number): void {
    this.currentWave = 0;
    if (typeof maxWaves === 'number') {
      this.maxWaves = Math.max(1, maxWaves);
    }
    this.state = 'IDLE';
    this.isTerminal = false;
    this.isNotifying = false;
  }
}
