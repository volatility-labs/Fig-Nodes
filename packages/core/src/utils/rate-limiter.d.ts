/**
 * Simple rate limiter using token bucket algorithm.
 */
export declare class RateLimiter {
    private maxPerSecond;
    private tokens;
    private lastRefill;
    constructor(maxPerSecond?: number);
    private refillTokens;
    acquire(): Promise<void>;
    private sleep;
}
