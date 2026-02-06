// src/utils/rate-limiter.ts
// Token bucket rate limiter
/**
 * Simple rate limiter using token bucket algorithm.
 */
export class RateLimiter {
    maxPerSecond;
    tokens;
    lastRefill;
    constructor(maxPerSecond = 100) {
        this.maxPerSecond = maxPerSecond;
        this.tokens = maxPerSecond;
        this.lastRefill = Date.now();
    }
    refillTokens() {
        const now = Date.now();
        const elapsed = (now - this.lastRefill) / 1000; // seconds
        const tokensToAdd = elapsed * this.maxPerSecond;
        this.tokens = Math.min(this.maxPerSecond, this.tokens + tokensToAdd);
        this.lastRefill = now;
    }
    async acquire() {
        this.refillTokens();
        if (this.tokens >= 1) {
            this.tokens -= 1;
            return;
        }
        // Wait until a token is available
        const waitTime = ((1 - this.tokens) / this.maxPerSecond) * 1000;
        await this.sleep(waitTime);
        this.refillTokens();
        this.tokens -= 1;
    }
    sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
}
