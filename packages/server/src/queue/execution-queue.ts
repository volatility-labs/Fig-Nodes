// Execution queue for managing graph execution jobs
import type { WebSocket } from '@fastify/websocket';
import type { Graph } from '@fig-node/core';
import {
  type ExecutionJob,
  JobState,
  createExecutionJob,
  createDeferred,
  type Deferred,
} from '../types/job.js';
import { buildQueuePositionMessage } from '../types/messages.js';
import { wsSendAsync, isWsConnected } from '../websocket/send-utils.js';

const POSITION_UPDATE_INTERVAL_MS = 1000;

/**
 * ExecutionQueue manages a FIFO queue of graph execution jobs.
 * Only one job runs at a time (sequential execution).
 *
 * TypeScript equivalent of the Python ExecutionQueue class.
 */
export class ExecutionQueue {
  private pending: ExecutionJob[] = [];
  private running: ExecutionJob | null = null;
  private jobIdCounter = 0;
  private shuttingDown = false;

  /** Wakeup signal for the worker - resolves when a job is available */
  private wakeup: Deferred<void> = createDeferred();

  /**
   * Enqueue a new job for execution.
   * Starts sending queue position updates to the client.
   */
  enqueue(websocket: WebSocket, graphData: Graph): ExecutionJob {
    const job = createExecutionJob(++this.jobIdCounter, websocket, graphData);

    this.pending.push(job);

    // Start position update interval
    this.startPositionUpdates(job);

    // Wake up the worker if it's waiting (atomic swap: create new deferred before resolving old)
    const prev = this.wakeup;
    this.wakeup = createDeferred();
    prev.resolve();

    return job;
  }

  /**
   * Get the next pending job (blocks until one is available).
   * Called by the execution worker.
   */
  async getNext(): Promise<ExecutionJob | null> {
    while (!this.shuttingDown) {
      if (this.pending.length > 0) {
        const job = this.pending.shift()!;

        // Stop position updates and clear interval
        this.stopPositionUpdates(job);

        // Mark as running
        job.state = JobState.RUNNING;
        this.running = job;

        return job;
      }

      // Wait for a job to be enqueued
      await this.wakeup.promise;
    }

    return null;
  }

  /**
   * Mark a job as done. Resolves the job's done promise.
   */
  markDone(job: ExecutionJob): void {
    if (job.state !== JobState.DONE) {
      job.state = JobState.DONE;
    }

    if (this.running === job) {
      this.running = null;
    }

    // Stop any remaining position updates
    this.stopPositionUpdates(job);

    // Signal completion
    job.done.resolve();
  }

  /**
   * Cancel a job. If pending, removes from queue. If running, signals cancellation.
   */
  cancelJob(job: ExecutionJob): void {
    if (job.state === JobState.CANCELLED || job.state === JobState.DONE) {
      return; // Already cancelled or done
    }

    job.state = JobState.CANCELLED;

    // Stop position updates
    this.stopPositionUpdates(job);

    // Remove from pending queue if present
    const pendingIndex = this.pending.indexOf(job);
    if (pendingIndex !== -1) {
      this.pending.splice(pendingIndex, 1);
      // If it was pending, we can resolve done immediately
      job.done.resolve();
    }

    // Signal cancellation to the executor via AbortController
    job.cancelController.abort();
  }

  /**
   * Get the queue position of a job.
   * Returns 0 if running, 1+ if pending, -1 if not found.
   */
  getPosition(job: ExecutionJob): number {
    if (this.running === job) {
      return 0;
    }

    const index = this.pending.indexOf(job);
    if (index !== -1) {
      return index + 1; // 1-indexed for display
    }

    return -1;
  }

  /**
   * Shutdown the queue. Wakes up the worker so it can exit.
   */
  shutdown(): void {
    this.shuttingDown = true;

    // Cancel all pending jobs
    for (const job of this.pending) {
      this.cancelJob(job);
    }

    // Cancel running job if any
    if (this.running) {
      this.cancelJob(this.running);
    }

    // Wake up worker to exit
    this.wakeup.resolve();
  }

  /**
   * Get the current running job.
   */
  getRunning(): ExecutionJob | null {
    return this.running;
  }

  /**
   * Check if queue is shutting down.
   */
  isShuttingDown(): boolean {
    return this.shuttingDown;
  }

  // ============ Private Methods ============

  private startPositionUpdates(job: ExecutionJob): void {
    // Send initial position
    this.sendPositionUpdate(job);

    // Set up interval for periodic updates
    job.positionUpdateInterval = setInterval(() => {
      if (job.state === JobState.PENDING) {
        this.sendPositionUpdate(job);
      } else {
        this.stopPositionUpdates(job);
      }
    }, POSITION_UPDATE_INTERVAL_MS);
  }

  private stopPositionUpdates(job: ExecutionJob): void {
    if (job.positionUpdateInterval) {
      clearInterval(job.positionUpdateInterval);
      job.positionUpdateInterval = undefined;
    }
  }

  private sendPositionUpdate(job: ExecutionJob): void {
    if (!isWsConnected(job.websocket)) {
      return;
    }

    const position = this.getPosition(job);
    if (position >= 0) {
      const message = buildQueuePositionMessage(position, job.id);
      wsSendAsync(job.websocket, message);
    }
  }
}
