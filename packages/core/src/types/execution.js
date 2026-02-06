// src/types/execution.ts
// Execution result types, progress events, and callbacks
import { ExecutionOutcome, AssetSymbol } from './domain';
export const ExecutionResultFactory = {
    success(results) {
        return { outcome: ExecutionOutcome.SUCCESS, results, error: null, cancelledBy: null };
    },
    cancelled(by = 'user') {
        return { outcome: ExecutionOutcome.CANCELLED, results: null, error: null, cancelledBy: by };
    },
    error(errorMsg) {
        return { outcome: ExecutionOutcome.ERROR, results: null, error: errorMsg, cancelledBy: null };
    },
    isSuccess(result) {
        return result.outcome === ExecutionOutcome.SUCCESS;
    },
    isCancelled(result) {
        return result.outcome === ExecutionOutcome.CANCELLED;
    },
};
// ============ Serialization Helper ============
export function serializeForApi(obj) {
    if (obj === null || obj === undefined) {
        return obj;
    }
    if (Array.isArray(obj)) {
        return obj.map(serializeForApi);
    }
    if (obj instanceof AssetSymbol) {
        return obj.toDict();
    }
    if (typeof obj === 'object') {
        const result = {};
        for (const [key, value] of Object.entries(obj)) {
            result[key] = serializeForApi(value);
        }
        return result;
    }
    return obj;
}
