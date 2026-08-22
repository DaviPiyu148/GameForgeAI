import type { WorldEventDef } from './types';

export class WorldEventManager {
  private events: WorldEventDef[] = [];
  private activeEvents: Map<string, { event: WorldEventDef; timeRemaining: number }> = new Map();
  private onEventStarted?: (event: WorldEventDef) => void;
  private onEventEnded?: (event: WorldEventDef) => void;

  constructor(
    events: WorldEventDef[] = [],
    onEventStarted?: (event: WorldEventDef) => void,
    onEventEnded?: (event: WorldEventDef) => void
  ) {
    this.events = events;
    this.onEventStarted = onEventStarted;
    this.onEventEnded = onEventEnded;

    for (const evt of this.events) {
      if (evt.active) {
        this.triggerEvent(evt.id);
      }
    }
  }

  public getActiveEvents(): WorldEventDef[] {
    return Array.from(this.activeEvents.values()).map((v) => v.event);
  }

  public triggerEvent(eventId: string): boolean {
    const evt = this.events.find((e) => e.id === eventId);
    if (!evt || this.activeEvents.has(eventId)) return false;

    this.activeEvents.set(eventId, {
      event: evt,
      timeRemaining: evt.duration_seconds || 60,
    });
    evt.active = true;

    if (this.onEventStarted) {
      this.onEventStarted(evt);
    }
    return true;
  }

  public update(deltaSeconds: number): void {
    for (const [id, item] of this.activeEvents.entries()) {
      item.timeRemaining -= deltaSeconds;
      if (item.timeRemaining <= 0) {
        item.event.active = false;
        this.activeEvents.delete(id);
        if (this.onEventEnded) {
          this.onEventEnded(item.event);
        }
      }
    }
  }
}
