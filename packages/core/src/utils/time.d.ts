import { AssetClass } from '../types';
/**
 * Check if US stock market is currently open (9:30 AM ET - 4:00 PM ET, Mon-Fri).
 */
export declare function isUSMarketOpen(): boolean;
/**
 * Convert Eastern Time to UTC timestamp in milliseconds.
 */
export declare function etTimeToUtcTimestampMs(year: number, month: number, day: number, hour: number, minute: number): number;
/**
 * Convert UTC timestamp in milliseconds to Eastern Time date object.
 */
export declare function utcTimestampMsToEtDatetime(timestampMs: number): Date;
/**
 * Format a date in Eastern Time timezone.
 */
export declare function formatInEasternTime(date: Date, options?: Intl.DateTimeFormatOptions): string;
/**
 * Create a market open time date in Eastern Timezone.
 */
export declare function createMarketOpenTime(year: number, month: number, day: number, hour?: number, minute?: number): Date;
/**
 * Parse timestamp with auto-detection of unit (s, ms, ns) and convert to ET datetime.
 */
export declare function utcTimestampFlexToEtDatetime(ts: number): Date | null;
/**
 * Get the appropriate timezone string for an asset class.
 */
export declare function getTimezoneForAssetClass(assetClass: AssetClass): string;
/**
 * Convert UTC timestamp in milliseconds to datetime in target timezone.
 */
export declare function utcTimestampMsToDatetime(timestampMs: number, _targetTimezone?: string): Date;
/**
 * Convert list of UTC timestamps (ms) to formatted datetime strings in appropriate timezone.
 */
export declare function convertTimestampsToDatetimes(timestampsMs: number[], assetClass: AssetClass): Date[];
/**
 * Format date in specific timezone.
 */
export declare function formatDateInTimezone(date: Date, timezone: string, options?: Intl.DateTimeFormatOptions): string;
