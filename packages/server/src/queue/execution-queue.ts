// Single-flight execution controller for graph execution jobs
import type { WebSocket } from '@fastify/websocket';
import type { Graph } from '@sosa/core';
import {
  type ExecutionJob,
  JobState,
  createExecutionJob,
  createDeferred,
  type Deferred,
} from '../types/job.js';

/**
 * ExecutionQueue manages single-flight graph execution.
 * Exactly one job may be active (pending/running) at a time.
 * Additional enqueue attempts are rejected.
 */
export class ExecutionQueue {
  private next: ExecutionJob | null = null;
  private running: ExecutionJob | null = null;
  private jobIdCounter = 0;
  private shuttingDown = false;

  /** Wakeup signal for the worker - resolves when a job is available */
  private wakeup: Deferred<void> = createDeferred();

  /**
   * Enqueue a new job for execution.
   * Returns null when an execution is already active.
   */
  enqueue(websocket: WebSocket, graphData: Graph): ExecutionJob | null {
    if (this.shuttingDown || this.next || this.running) {
      return null;
    }

    const job = createExecutionJob(++this.jobIdCounter, websocket, graphData);
    this.next = job;

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
      if (this.next) {
        const job = this.next;
        this.next = null;
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

    // Cancel queued-but-not-started job immediately.
    if (this.next === job) {
      this.next = null;
      job.done.resolve();
    } else if (this.running === job) {
      this.running = null;
    }

    // Signal cancellation to the executor via AbortController
    job.cancelController.abort();
  }

  /**
   * Shutdown the queue. Wakes up the worker so it can exit.
   */
  shutdown(): void {
    this.shuttingDown = true;

    // Cancel queued job
    if (this.next) {
      this.cancelJob(this.next);
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
   * Get the current queued-but-not-yet-running job.
   */
  getNextQueued(): ExecutionJob | null {
    return this.next;
  }

  /**
   * Check if queue is shutting down.
   */
  isShuttingDown(): boolean {
    return this.shuttingDown;
  }
}
