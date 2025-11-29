/**
 * Window interface extensions for global services
 * 
 * This file extends the Window interface to include custom properties
 * that are attached to the window object at runtime.
 */

import type { ServiceRegistry } from '../services/ServiceRegistry';
import type { PerformanceProfiler } from '../services/PerformanceProfiler';

declare global {
    interface Window {
        /**
         * Service registry instance for accessing application services
         * @example
         * const sr = window.serviceRegistry;
         * const statusService = sr?.get('statusService');
         */
        serviceRegistry?: ServiceRegistry;
        
        /**
         * Performance profiler instance for measuring application performance
         * @example
         * const profiler = window.performanceProfiler;
         * profiler?.startMeasure('operation');
         */
        performanceProfiler?: PerformanceProfiler;
    }
}

export {};

