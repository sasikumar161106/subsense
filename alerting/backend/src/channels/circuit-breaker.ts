export enum CircuitState {
  CLOSED = 'CLOSED',       // Normal operation: requests go to primary
  OPEN = 'OPEN',           // Unhealthy: requests route to secondary backup
  HALF_OPEN = 'HALF_OPEN'  // Testing primary health after cooldown
}

export interface CircuitBreakerConfig {
  failureThreshold: number;   // Number of consecutive failures before tripping
  timeoutMs: number;          // Requests taking longer than this are considered failures (8000ms)
  cooldownPeriodMs: number;   // Time to wait before moving from OPEN to HALF_OPEN (10000ms)
}

export class CircuitBreaker {
  private name: string;
  private state: CircuitState = CircuitState.CLOSED;
  private consecutiveFailures: number = 0;
  private lastFailureTime: number = 0;
  private config: CircuitBreakerConfig;

  constructor(name: string, config?: Partial<CircuitBreakerConfig>) {
    this.name = name;
    this.config = {
      failureThreshold: 2,
      timeoutMs: 8000, // 8 seconds maximum latency
      cooldownPeriodMs: 10000,
      ...config
    };
  }

  public getState(): CircuitState {
    // If in OPEN state and cooldown has elapsed, transition to HALF_OPEN
    if (this.state === CircuitState.OPEN) {
      const elapsed = Date.now() - this.lastFailureTime;
      if (elapsed > this.config.cooldownPeriodMs) {
        this.state = CircuitState.HALF_OPEN;
        console.log(`[CIRCUIT BREAKER: ${this.name}] Cooldown elapsed. State transitioned to HALF_OPEN.`);
      }
    }
    return this.state;
  }

  public async execute<T>(
    primaryAction: () => Promise<T>,
    secondaryFallback: () => Promise<T>
  ): Promise<{ result: T; usedSecondary: boolean }> {
    const currentState = this.getState();

    if (currentState === CircuitState.OPEN) {
      console.warn(
        `[CIRCUIT BREAKER: ${this.name}] Circuit is OPEN. Immediately routing to SECONDARY backup provider.`
      );
      const result = await secondaryFallback();
      return { result, usedSecondary: true };
    }

    try {
      // Execute primary action with timeout guard (< 8s)
      const result = await this.executeWithTimeout(primaryAction, this.config.timeoutMs);
      this.recordSuccess();
      return { result, usedSecondary: false };
    } catch (err: any) {
      console.error(
        `[CIRCUIT BREAKER: ${this.name}] Primary provider failed: ${err.message}. Recording failure.`
      );
      this.recordFailure();

      console.warn(
        `[CIRCUIT BREAKER: ${this.name}] Failover initiated. Routing request to SECONDARY backup provider.`
      );
      const result = await secondaryFallback();
      return { result, usedSecondary: true };
    }
  }

  private async executeWithTimeout<T>(action: () => Promise<T>, timeoutMs: number): Promise<T> {
    let timer: NodeJS.Timeout;
    const timeoutPromise = new Promise<T>((_, reject) => {
      timer = setTimeout(() => {
        reject(new Error(`Primary request exceeded latency threshold of ${timeoutMs}ms`));
      }, timeoutMs);
    });

    try {
      return await Promise.race([action(), timeoutPromise]);
    } finally {
      clearTimeout(timer!);
    }
  }

  public recordSuccess(): void {
    if (this.state === CircuitState.HALF_OPEN) {
      console.log(`[CIRCUIT BREAKER: ${this.name}] Probe succeeded. Circuit reset to CLOSED.`);
    }
    this.consecutiveFailures = 0;
    this.state = CircuitState.CLOSED;
  }

  public recordFailure(): void {
    this.consecutiveFailures++;
    this.lastFailureTime = Date.now();

    if (this.consecutiveFailures >= this.config.failureThreshold || this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
      console.warn(
        `[CIRCUIT BREAKER: ${this.name}] >>> CIRCUIT TRIPPED TO OPEN! Consecutive failures: ${this.consecutiveFailures} <<<`
      );
    }
  }

  public trip(): void {
    this.consecutiveFailures = this.config.failureThreshold;
    this.lastFailureTime = Date.now();
    this.state = CircuitState.OPEN;
    console.warn(`[CIRCUIT BREAKER: ${this.name}] Force-tripped to OPEN.`);
  }

  public reset(): void {
    this.consecutiveFailures = 0;
    this.state = CircuitState.CLOSED;
    console.log(`[CIRCUIT BREAKER: ${this.name}] Force-reset to CLOSED.`);
  }
}
