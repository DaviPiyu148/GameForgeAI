export type RuntimeLifecycleState =
  | 'LOADING'
  | 'READY'
  | 'ACTIVE'
  | 'PAUSED'
  | 'TRANSITIONING'
  | 'WON'
  | 'LOST'
  | 'DESTROYED';

export interface StateTransitionEvent {
  from: RuntimeLifecycleState;
  to: RuntimeLifecycleState;
  reason?: string;
  timestamp: number;
}

export class RuntimeStateMachine {
  private state: RuntimeLifecycleState = 'LOADING';
  private endReason?: string;
  private onStateChange?: (event: StateTransitionEvent) => void;

  constructor(
    initialState: RuntimeLifecycleState = 'LOADING',
    onStateChange?: (event: StateTransitionEvent) => void
  ) {
    this.state = initialState;
    this.onStateChange = onStateChange;
  }

  public getState(): RuntimeLifecycleState {
    return this.state;
  }

  public getEndReason(): string | undefined {
    return this.endReason;
  }

  public isTerminal(): boolean {
    return this.state === 'WON' || this.state === 'LOST' || this.state === 'DESTROYED';
  }

  public canMutateGameplay(): boolean {
    return this.state === 'ACTIVE';
  }

  public isPaused(): boolean {
    return this.state === 'PAUSED';
  }

  public isTransitioning(): boolean {
    return this.state === 'TRANSITIONING';
  }

  public transitionTo(nextState: RuntimeLifecycleState, reason?: string): boolean {
    if (this.state === nextState) return false;

    // Terminal states cannot be transitioned out of (except explicit scene destroy)
    if (this.isTerminal() && nextState !== 'DESTROYED') {
      console.warn(`[RuntimeStateMachine] Blocked invalid transition from terminal state ${this.state} to ${nextState}.`);
      return false;
    }

    const prev = this.state;
    this.state = nextState;
    if (reason) {
      this.endReason = reason;
    }

    if (this.onStateChange) {
      this.onStateChange({
        from: prev,
        to: nextState,
        reason,
        timestamp: Date.now(),
      });
    }

    return true;
  }

  public setReady(): boolean {
    return this.transitionTo('READY');
  }

  public setActive(): boolean {
    return this.transitionTo('ACTIVE');
  }

  public setPaused(paused: boolean): boolean {
    if (paused && this.state === 'ACTIVE') {
      return this.transitionTo('PAUSED');
    } else if (!paused && this.state === 'PAUSED') {
      return this.transitionTo('ACTIVE');
    }
    return false;
  }

  public beginTransition(reason: string = 'STAGE_TRANSITION'): boolean {
    if (this.isTerminal()) return false;
    return this.transitionTo('TRANSITIONING', reason);
  }

  public endTransition(): boolean {
    if (this.state === 'TRANSITIONING') {
      return this.transitionTo('ACTIVE');
    }
    return false;
  }

  public setWon(reason: string = 'VICTORY'): boolean {
    if (this.isTerminal()) return false;
    return this.transitionTo('WON', reason);
  }

  public setLost(reason: string = 'MISSION FAILED'): boolean {
    if (this.isTerminal()) return false;
    return this.transitionTo('LOST', reason);
  }

  public destroy(): void {
    this.transitionTo('DESTROYED', 'SCENE_DESTROYED');
  }
}
