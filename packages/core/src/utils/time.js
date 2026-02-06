// src/utils/time.ts
// Timezone conversion utilities (ET <-> UTC)
import { AssetClass } from '../types';
/**
 * Check if US stock market is currently open (9:30 AM ET - 4:00 PM ET, Mon-Fri).
 */
export function isUSMarketOpen() {
    const now = new Date();
    // Convert to ET (handles DST automatically)
    const etFormatter = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        hour: 'numeric',
        minute: 'numeric',
        hour12: false,
        weekday: 'short',
    });
    const parts = etFormatter.formatToParts(now);
    const weekday = parts.find((p) => p.type === 'weekday')?.value || '';
    const hour = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10);
    const minute = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10);
    // Check if it's a weekday
    if (['Sat', 'Sun'].includes(weekday)) {
        return false;
    }
    // Check if within market hours (9:30 AM - 4:00 PM ET)
    const currentMinutes = hour * 60 + minute;
    const marketOpenMinutes = 9 * 60 + 30; // 9:30 AM
    const marketCloseMinutes = 16 * 60; // 4:00 PM
    return currentMinutes >= marketOpenMinutes && currentMinutes <= marketCloseMinutes;
}
/**
 * Convert Eastern Time to UTC timestamp in milliseconds.
 */
export function etTimeToUtcTimestampMs(year, month, day, hour, minute) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`;
    const date = new Date(dateStr);
    const utcDate = new Date(date.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    const etOffset = date.getTime() - utcDate.getTime();
    return date.getTime() - etOffset;
}
/**
 * Convert UTC timestamp in milliseconds to Eastern Time date object.
 */
export function utcTimestampMsToEtDatetime(timestampMs) {
    const date = new Date(timestampMs);
    return date;
}
/**
 * Format a date in Eastern Time timezone.
 */
export function formatInEasternTime(date, options) {
    const defaultOptions = {
        timeZone: 'America/New_York',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    };
    return date.toLocaleString('en-US', { ...defaultOptions, ...options });
}
/**
 * Create a market open time date in Eastern Timezone.
 */
export function createMarketOpenTime(year, month, day, hour = 9, minute = 30) {
    return new Date(new Date(`${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`).toLocaleString('en-US', { timeZone: 'America/New_York' }));
}
/**
 * Parse timestamp with auto-detection of unit (s, ms, ns) and convert to ET datetime.
 */
export function utcTimestampFlexToEtDatetime(ts) {
    if (ts <= 0) {
        console.warn(`Invalid timestamp ${ts} (<=0); returning null`);
        return null;
    }
    const tsStr = String(ts);
    const digitCount = tsStr.length;
    const candidates = [
        { unit: 'ns', divisor: 1000000 },
        { unit: 'ms', divisor: 1 },
        { unit: 's', divisor: 0.001 },
    ];
    for (const { divisor: d } of candidates) {
        const timestampMs = d === 0.001 ? ts * 1000 : ts / d;
        const date = new Date(timestampMs);
        const year = date.getUTCFullYear();
        if (year >= 1970 && year <= 2100) {
            return date;
        }
    }
    console.warn(`Could not parse timestamp ${ts} (digits: ${digitCount}); all units invalid`);
    return null;
}
/**
 * Get the appropriate timezone string for an asset class.
 */
export function getTimezoneForAssetClass(assetClass) {
    if (assetClass === AssetClass.CRYPTO) {
        return 'UTC';
    }
    else if (assetClass === AssetClass.STOCKS) {
        return 'America/New_York';
    }
    else {
        console.warn(`Unknown asset class ${assetClass}, defaulting to UTC`);
        return 'UTC';
    }
}
/**
 * Convert UTC timestamp in milliseconds to datetime in target timezone.
 */
export function utcTimestampMsToDatetime(timestampMs, _targetTimezone) {
    const date = new Date(timestampMs);
    return date;
}
/**
 * Convert list of UTC timestamps (ms) to formatted datetime strings in appropriate timezone.
 */
export function convertTimestampsToDatetimes(timestampsMs, assetClass) {
    const targetTimezone = getTimezoneForAssetClass(assetClass);
    return timestampsMs.map((ts) => utcTimestampMsToDatetime(ts, targetTimezone));
}
/**
 * Format date in specific timezone.
 */
export function formatDateInTimezone(date, timezone, options) {
    const defaultOptions = {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    };
    return date.toLocaleString('en-US', { ...defaultOptions, ...options });
}
