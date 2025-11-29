/**
 * Performance Profiler
 * Tracks performance metrics to identify bottlenecks in graph rendering and data processing
 */

interface PerformanceMetric {
    name: string;
    startTime: number;
    endTime?: number;
    duration?: number;
    metadata?: Record<string, unknown>;
}

interface FrameMetrics {
    frameNumber: number;
    timestamp: number;
    frameTime: number;
    renderCalls: number;
    nodesUpdated: number;
    memoryUsed?: number;
}

interface ProfilerStats {
    totalFrames: number;
    averageFrameTime: number;
    maxFrameTime: number;
    minFrameTime: number;
    droppedFrames: number;
    totalRenderCalls: number;
    totalNodeUpdates: number;
    peakMemoryUsage?: number;
    metrics: PerformanceMetric[];
    frameHistory: FrameMetrics[];
}

export class PerformanceProfiler {
    private static instance: PerformanceProfiler | null = null;
    private isProfiling: boolean = false;
    private startTime: number = 0;
    private metrics: PerformanceMetric[] = [];
    private frameHistory: FrameMetrics[] = [];
    private frameCounter: number = 0;
    private lastFrameTime: number = 0;
    private renderCallCount: number = 0;
    private nodeUpdateCount: number = 0;
    private rafId: number | null = null;
    private maxHistorySize: number = 300; // Keep last 5 seconds at 60fps

    private constructor() {
        // Private constructor for singleton
    }

    static getInstance(): PerformanceProfiler {
        if (!PerformanceProfiler.instance) {
            PerformanceProfiler.instance = new PerformanceProfiler();
        }
        return PerformanceProfiler.instance;
    }

    /**
     * Start profiling session
     */
    start(): void {
        if (this.isProfiling) {
            console.warn('Profiler already running');
            return;
        }

        this.isProfiling = true;
        this.startTime = performance.now();
        this.metrics = [];
        this.frameHistory = [];
        this.frameCounter = 0;
        this.lastFrameTime = this.startTime;
        this.renderCallCount = 0;
        this.nodeUpdateCount = 0;

        // Start frame monitoring
        this.monitorFrames();

        console.log('🔍 Performance profiler started');
    }

    /**
     * Stop profiling session
     */
    stop(): ProfilerStats {
        if (!this.isProfiling) {
            console.warn('Profiler not running');
            return this.getStats();
        }

        this.isProfiling = false;
        if (this.rafId !== null) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }

        const stats = this.getStats();
        console.log('🔍 Performance profiler stopped', stats);
        return stats;
    }

    /**
     * Measure a specific operation
     * Automatically tracks duration and handles errors
     */
    measure(name: string, fn: () => void): void;
    measure<T>(name: string, fn: () => T): T;
    measure<T>(name: string, fn: () => T, metadata?: Record<string, unknown>): T;
    measure<T>(name: string, fn: () => T, metadata?: Record<string, unknown>): T {
        if (!this.isProfiling) {
            return fn();
        }

        const startTime = performance.now();
        let result: T;
        let error: Error | null = null;
        try {
            result = fn();
        } catch (e) {
            error = e instanceof Error ? e : new Error(String(e));
            throw e;
        } finally {
            const endTime = performance.now();
            this.metrics.push({
                name,
                startTime,
                endTime,
                duration: endTime - startTime,
                metadata: {
                    ...metadata,
                    ...(error ? { error: error.message } : {})
                }
            });
        }
        return result;
    }

    /**
     * Start a custom metric measurement
     */
    startMetric(name: string, metadata?: Record<string, unknown>): void {
        if (!this.isProfiling) return;

        this.metrics.push({
            name,
            startTime: performance.now(),
            metadata
        });
    }

    /**
     * End a custom metric measurement
     */
    endMetric(name: string): number | null {
        if (!this.isProfiling) return null;

        const metric = this.metrics
            .filter(m => m.name === name && m.endTime === undefined)
            .pop();

        if (!metric) {
            console.warn(`No active metric found for: ${name}`);
            return null;
        }

        metric.endTime = performance.now();
        metric.duration = metric.endTime - metric.startTime;
        return metric.duration;
    }

    /**
     * Track a render call
     */
    trackRenderCall(): void {
        if (!this.isProfiling) return;
        this.renderCallCount++;
    }

    /**
     * Track a node update
     */
    trackNodeUpdate(count: number = 1): void {
        if (!this.isProfiling) return;
        this.nodeUpdateCount += count;
    }

    /**
     * Monitor frame performance
     */
    private monitorFrames(): void {
        const measureFrame = (timestamp: number) => {
            if (!this.isProfiling) return;

            const frameTime = timestamp - this.lastFrameTime;
            this.lastFrameTime = timestamp;

            // Get memory usage if available
            let memoryUsed: number | undefined;
            if ('memory' in performance) {
                const mem = (performance as any).memory;
                memoryUsed = mem.usedJSHeapSize;
            }

            const frameMetric: FrameMetrics = {
                frameNumber: this.frameCounter++,
                timestamp,
                frameTime,
                renderCalls: this.renderCallCount,
                nodesUpdated: this.nodeUpdateCount,
                memoryUsed
            };

            this.frameHistory.push(frameMetric);

            // Keep history size manageable
            if (this.frameHistory.length > this.maxHistorySize) {
                this.frameHistory.shift();
            }

            // Reset counters for next frame
            this.renderCallCount = 0;
            this.nodeUpdateCount = 0;

            this.rafId = requestAnimationFrame(measureFrame);
        };

        this.rafId = requestAnimationFrame(measureFrame);
    }

    /**
     * Get current profiling statistics
     */
    getStats(): ProfilerStats {
        const completedMetrics = this.metrics.filter(m => m.duration !== undefined);
        const frameTimes = this.frameHistory.map(f => f.frameTime);
        
        const totalFrames = this.frameHistory.length;
        const averageFrameTime = frameTimes.length > 0
            ? frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length
            : 0;
        const maxFrameTime = frameTimes.length > 0 ? Math.max(...frameTimes) : 0;
        const minFrameTime = frameTimes.length > 0 ? Math.min(...frameTimes) : 0;
        
        // Count dropped frames (frames taking longer than 16.67ms at 60fps)
        const droppedFrames = frameTimes.filter(t => t > 16.67).length;
        
        const totalRenderCalls = this.frameHistory.reduce((sum, f) => sum + f.renderCalls, 0);
        const totalNodeUpdates = this.frameHistory.reduce((sum, f) => sum + f.nodesUpdated, 0);
        
        const memoryValues = this.frameHistory
            .map(f => f.memoryUsed)
            .filter((m): m is number => m !== undefined);
        const peakMemoryUsage = memoryValues.length > 0 ? Math.max(...memoryValues) : undefined;

        return {
            totalFrames,
            averageFrameTime,
            maxFrameTime,
            minFrameTime,
            droppedFrames,
            totalRenderCalls,
            totalNodeUpdates,
            peakMemoryUsage,
            metrics: completedMetrics,
            frameHistory: [...this.frameHistory]
        };
    }

    /**
     * Get metrics by name
     */
    getMetricsByName(name: string): PerformanceMetric[] {
        return this.metrics.filter(m => m.name === name && m.duration !== undefined);
    }

    /**
     * Get average duration for a metric
     */
    getAverageMetricDuration(name: string): number {
        const metrics = this.getMetricsByName(name);
        if (metrics.length === 0) return 0;
        const total = metrics.reduce((sum, m) => sum + (m.duration || 0), 0);
        return total / metrics.length;
    }

    /**
     * Export profiling data as JSON
     */
    exportData(): string {
        return JSON.stringify({
            stats: this.getStats(),
            timestamp: new Date().toISOString()
        }, null, 2);
    }

    /**
     * Display profiling results in console with detailed analysis
     */
    logResults(): void {
        const stats = this.getStats();
        
        console.group('🔍 Performance Profiling Results');
        console.log(`Total Frames: ${stats.totalFrames}`);
        console.log(`Average Frame Time: ${stats.averageFrameTime.toFixed(2)}ms`);
        console.log(`Max Frame Time: ${stats.maxFrameTime.toFixed(2)}ms`);
        console.log(`Min Frame Time: ${stats.minFrameTime.toFixed(2)}ms`);
        const dropPercentage = stats.totalFrames > 0 
            ? ((stats.droppedFrames / stats.totalFrames) * 100).toFixed(1)
            : '0.0';
        console.log(`Dropped Frames: ${stats.droppedFrames} (${dropPercentage}%)`);
        console.log(`Total Render Calls: ${stats.totalRenderCalls}`);
        console.log(`Total Node Updates: ${stats.totalNodeUpdates}`);
        
        if (stats.peakMemoryUsage) {
            console.log(`Peak Memory Usage: ${(stats.peakMemoryUsage / 1024 / 1024).toFixed(2)} MB`);
        }

        // Performance warnings
        if (stats.averageFrameTime > 16.67) {
            console.warn(`⚠️ Average frame time (${stats.averageFrameTime.toFixed(2)}ms) exceeds 16.67ms target for 60fps`);
        }
        if (stats.droppedFrames > stats.totalFrames * 0.1) {
            console.warn(`⚠️ High dropped frame rate: ${dropPercentage}%`);
        }

        // Group metrics by name
        const metricGroups = new Map<string, PerformanceMetric[]>();
        stats.metrics.forEach(m => {
            if (!metricGroups.has(m.name)) {
                metricGroups.set(m.name, []);
            }
            metricGroups.get(m.name)!.push(m);
        });

        console.group('📊 Custom Metrics');
        metricGroups.forEach((metrics, name) => {
            const durations = metrics.map(m => m.duration || 0);
            const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length;
            const max = Math.max(...durations);
            const min = Math.min(...durations);
            const total = durations.reduce((sum, d) => sum + d, 0);
            console.log(`${name}: avg=${avg.toFixed(2)}ms, max=${max.toFixed(2)}ms, min=${min.toFixed(2)}ms, total=${total.toFixed(2)}ms, count=${metrics.length}`);
            
            // Highlight slow operations
            if (avg > 10) {
                console.warn(`  ⚠️ ${name} is slow (avg ${avg.toFixed(2)}ms)`);
            }
        });
        console.groupEnd();

        console.groupEnd();
    }

    /**
     * Print profiling results to console (alias for logResults for consistency)
     */
    printStatsToConsole(): void {
        this.logResults();
    }

    /**
     * Check if currently profiling
     */
    isActive(): boolean {
        return this.isProfiling;
    }
}

