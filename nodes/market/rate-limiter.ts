// Token bucket rate limiter

/**
 * Simple rate limiter using token bucket algorithm.
 */
export class RateLimiter {
  private maxPerSecond: number;
  private tokens: number;
  private lastRefill: number;

  constructor(maxPerSecond: number = 100) {
    this.maxPerSecond = maxPerSecond;
    this.tokens = maxPerSecond;
    this.lastRefill = Date.now();
  }

  private refillTokens(): void {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    const tokensToAdd = elapsed * this.maxPerSecond;
    this.tokens = Math.min(this.maxPerSecond, this.tokens + tokensToAdd);
    this.lastRefill = now;
  }

  async acquire(): Promise<void> {
    this.refillTokens();

    if (this.tokens >= 1) {
      this.tokens -= 1;
      return;
    }

    const waitTime = ((1 - this.tokens) / this.maxPerSecond) * 1000;
    await this.sleep(waitTime);
    this.refillTokens();
    this.tokens -= 1;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
