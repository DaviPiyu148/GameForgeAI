import type { PlaytestSummary, TelemetryEvent, TelemetryEventType } from './types';

export class TelemetryTracker {
  private startTime: number = 0;
  private endTime: number = 0;
  private events: TelemetryEvent[] = [];

  private score: number = 0;
  private damageTaken: number = 0;
  private damageDealt: number = 0;
  private enemiesDefeated: number = 0;
  private collectiblesGathered: number = 0;
  private objectivesCompleted: number = 0;
  private wavesReached: number = 1;
  private phaseReached: string = 'EARLY';
  private outcome: 'WON' | 'LOST' | 'ABANDONED' | 'PLAYED' = 'PLAYED';
  private isEnded: boolean = false;

  public startSession(): void {
    this.startTime = Date.now();
    this.events = [];
    this.score = 0;
    this.damageTaken = 0;
    this.damageDealt = 0;
    this.enemiesDefeated = 0;
    this.collectiblesGathered = 0;
    this.objectivesCompleted = 0;
    this.wavesReached = 1;
    this.phaseReached = 'EARLY';
    this.outcome = 'PLAYED';
    this.isEnded = false;

    this.record('SESSION_STARTED');
  }

  public record(type: TelemetryEventType, data?: Record<string, any>): void {
    const timestamp = Date.now();

    // Bounded event cap (150 max) to prevent memory growth. The terminal
    // SESSION_ENDED/SESSION_END marker must never be silently dropped by the cap — if
    // the cap is already full, evict the oldest event to make room for it rather than
    // discarding the one event any downstream analysis expects to always be present.
    if (this.events.length < 150) {
      this.events.push({ type, timestamp, data });
    } else if (type === 'SESSION_ENDED' || type === 'SESSION_END') {
      this.events.shift();
      this.events.push({ type, timestamp, data });
    }

    switch (type) {
      case 'PLAYER_DAMAGE':
      case 'PLAYER_DAMAGED':
        this.damageTaken += data?.damage || 10;
        break;
      case 'PLAYER_DEATH':
      case 'PLAYER_DIED':
        this.outcome = 'LOST';
        break;
      case 'ENEMY_DEFEATED':
        this.enemiesDefeated += 1;
        this.damageDealt += data?.damageDealt || 20;
        break;
      case 'ITEM_COLLECTED':
      case 'COLLECTIBLE_COLLECTED':
        this.collectiblesGathered += 1;
        break;
      case 'OBJECTIVE_COMPLETED':
      case 'OBJECTIVE_PROGRESS':
        this.objectivesCompleted += 1;
        if (data?.wave) {
          this.wavesReached = Math.max(this.wavesReached, Number(data.wave));
        }
        break;
      case 'WAVE_STARTED':
      case 'WAVE_COMPLETED':
        if (data?.wave) {
          this.wavesReached = Math.max(this.wavesReached, Number(data.wave));
        }
        break;
      case 'PHASE_STARTED':
        if (data?.phase) {
          this.phaseReached = String(data.phase);
        }
        break;
      case 'SCORE_CHANGED':
        this.score = data?.score !== undefined ? Number(data.score) : this.score;
        break;
      case 'GAME_WON':
        this.outcome = 'WON';
        break;
      case 'GAME_LOST':
        this.outcome = 'LOST';
        break;
      case 'ACTIVITY_COMPLETED':
        this.objectivesCompleted += 1;
        break;
      case 'REGION_ENTERED':
      case 'POI_DISCOVERED':
      case 'ACTIVITY_STARTED':
      case 'ACTIVITY_FAILED':
      case 'VEHICLE_ENTERED':
      case 'VEHICLE_EXITED':
      case 'ALERT_CHANGED':
      case 'FACTION_REPUTATION_CHANGED':
      case 'WORLD_EVENT_STARTED':
      case 'WORLD_EVENT_ENDED':
        // Recorded in events array for AI critique
        break;
    }
  }

  public endSession(finalOutcome?: 'WON' | 'LOST' | 'ABANDONED'): PlaytestSummary {
    if (this.isEnded && this.endTime > 0) {
      // Return cached summary to avoid duplicate end emissions
      const durationSeconds = Math.max(1, Math.round((this.endTime - this.startTime) / 1000));
      return {
        duration_seconds: durationSeconds,
        score: this.score,
        damage_taken: this.damageTaken,
        damage_dealt: this.damageDealt,
        enemies_defeated: this.enemiesDefeated,
        collectibles_gathered: this.collectiblesGathered,
        objectives_completed: this.objectivesCompleted,
        waves_reached: this.wavesReached,
        phase_reached: this.phaseReached,
        outcome: this.outcome,
        telemetry_events: this.events.slice(-150),
      };
    }

    this.isEnded = true;
    this.endTime = Date.now();
    if (finalOutcome) {
      this.outcome = finalOutcome;
    }
    this.record('SESSION_ENDED', { outcome: this.outcome });

    const durationSeconds = Math.max(1, Math.round((this.endTime - this.startTime) / 1000));

    return {
      duration_seconds: durationSeconds,
      score: this.score,
      damage_taken: this.damageTaken,
      damage_dealt: this.damageDealt,
      enemies_defeated: this.enemiesDefeated,
      collectibles_gathered: this.collectiblesGathered,
      objectives_completed: this.objectivesCompleted,
      waves_reached: this.wavesReached,
      phase_reached: this.phaseReached,
      outcome: this.outcome,
      telemetry_events: this.events.slice(-150),
    };
  }
}
