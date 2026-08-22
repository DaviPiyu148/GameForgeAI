import type { WorldTimeDef } from './types';

export class WorldManager {
  private currentHour: number = 8;
  private currentMinute: number = 0;
  private timeScale: number = 60; // 1 real second = 1 game minute by default
  private dayNightCycle: boolean = true;
  private worldState: Map<string, number | string | boolean> = new Map();

  constructor(timeDef?: WorldTimeDef, initialState?: Record<string, number | string | boolean>) {
    if (timeDef) {
      this.currentHour = timeDef.start_hour ?? 8;
      this.timeScale = timeDef.time_scale ?? 60;
      this.dayNightCycle = timeDef.day_night_cycle ?? true;
    }
    if (initialState) {
      for (const [k, v] of Object.entries(initialState)) {
        this.worldState.set(k, v);
      }
    }
  }

  public update(deltaSeconds: number): void {
    // Advance game clock
    const minutesToAdd = deltaSeconds * (this.timeScale / 60);
    this.currentMinute += minutesToAdd;
    while (this.currentMinute >= 60) {
      this.currentMinute -= 60;
      this.currentHour = (this.currentHour + 1) % 24;
    }
  }

  public getHour(): number {
    return this.currentHour;
  }

  public getMinute(): number {
    return Math.floor(this.currentMinute);
  }

  public getFormattedTime(): string {
    const hh = String(this.currentHour).padStart(2, '0');
    const mm = String(Math.floor(this.currentMinute)).padStart(2, '0');
    return `${hh}:${mm}`;
  }

  public isDayTime(): boolean {
    return this.currentHour >= 6 && this.currentHour < 19;
  }

  public isDayNightEnabled(): boolean {
    return this.dayNightCycle;
  }

  public getState(key: string, defaultValue: number | string | boolean = false): number | string | boolean {
    return this.worldState.has(key) ? this.worldState.get(key)! : defaultValue;
  }

  public setState(key: string, value: number | string | boolean): void {
    this.worldState.set(key, value);
  }

  public getAllState(): Record<string, number | string | boolean> {
    const obj: Record<string, number | string | boolean> = {};
    for (const [k, v] of this.worldState.entries()) {
      obj[k] = v;
    }
    return obj;
  }
}
