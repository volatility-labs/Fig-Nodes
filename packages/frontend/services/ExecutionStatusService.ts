/**
 * ExecutionStatusService - Manages execution status UI state
 *
 * No longer depends on ServiceRegistry or LiteGraph.
 * Status is applied directly to DOM elements and can be read by React components.
 */

import { ExecutionState } from '../types/websocketType';

export type ConnectionStatus = 'connected' | 'disconnected' | 'loading' | 'executing' | 'stopping';

function mapExecutionStateToConnectionStatus(state: ExecutionState): ConnectionStatus {
  switch (state) {
    case ExecutionState.QUEUED:
      return 'loading';
    case ExecutionState.RUNNING:
      return 'executing';
    case ExecutionState.FINISHED:
    case ExecutionState.CANCELLED:
      return 'connected';
    case ExecutionState.ERROR:
      return 'disconnected';
    default:
      return 'executing';
  }
}

type JobUIState = {
  jobId: number | null;
  status: ConnectionStatus;
  message: string;
  progress: number | null;
  determinate: boolean;
  queuePosition: number | null;
};

export class ExecutionStatusService {
  private currentJobId: number | null = null;
  private jobs = new Map<number, JobUIState>();
  private currentState: ConnectionStatus = 'connected';

  setConnection(status: ConnectionStatus, message?: string) {
    this.currentState = status;
    const isIdle = status === 'connected';
    this.applyToDOM({
      jobId: this.currentJobId,
      status,
      message: message ?? this.labelFor(status),
      progress: isIdle ? 0 : null,
      determinate: isIdle,
      queuePosition: null,
    });
  }

  startConnecting() {
    this.currentState = 'loading';
    this.applyToDOM({
      jobId: this.currentJobId,
      status: 'loading',
      message: 'Starting...',
      progress: null,
      determinate: false,
      queuePosition: null,
    });
  }

  setStopping() {
    this.currentState = 'stopping';
    this.applyToDOM({
      jobId: this.currentJobId,
      status: 'stopping',
      message: 'Stopping...',
      progress: null,
      determinate: false,
      queuePosition: null,
    });
  }

  getState(): ConnectionStatus {
    return this.currentState;
  }

  adoptJob(jobId: number) {
    this.currentJobId = jobId;
    const st: JobUIState = this.jobs.get(jobId) ?? {
      jobId,
      status: 'loading',
      message: 'Queued',
      progress: null,
      determinate: false,
      queuePosition: null,
    };
    this.jobs.set(jobId, st);
    this.applyToDOM(st);
  }

  updateFromBackendState(backendState: ExecutionState, message: string, jobId: number) {
    const st = this.ensure(jobId);
    const frontendState = mapExecutionStateToConnectionStatus(backendState);

    st.status = frontendState;
    st.message = message;
    this.currentState = frontendState;

    if (backendState === ExecutionState.FINISHED) {
      st.progress = 100;
      st.determinate = true;
    } else if (backendState === ExecutionState.RUNNING) {
      st.progress = null;
      st.determinate = false;
    } else {
      st.progress = null;
      st.determinate = false;
    }

    this.applyIfActive(st);
  }

  setQueuePosition(jobId: number, position: number) {
    const st = this.ensure(jobId);
    st.queuePosition = position;
    st.message = position > 0 ? `Queued (${position} ahead)` : 'Starting...';
    st.status = position > 0 ? 'loading' : 'executing';
    this.currentState = position > 0 ? 'loading' : 'executing';
    this.applyIfActive(st);
  }

  setProgress(jobId: number | null, percent?: number, label?: string) {
    const st = this.ensure(jobId);
    if (typeof percent === 'number') {
      st.progress = Math.max(0, Math.min(100, percent));
      st.determinate = true;
    } else {
      st.progress = null;
      st.determinate = false;
    }
    if (label) {
      st.message = label;
    }
    st.status = 'executing';
    this.currentState = 'executing';
    this.applyIfActive(st);
  }

  stopped(jobId: number | null) {
    const st = this.ensure(jobId);
    st.message = 'Stopped';
    st.status = 'connected';
    st.progress = null;
    st.determinate = false;
    this.currentState = 'connected';
    this.applyIfActive(st);
    this.setIdle();
  }

  error(jobId: number | null, message: string) {
    const st = this.ensure(jobId);
    st.message = `Error: ${message}`;
    st.status = 'disconnected';
    st.progress = null;
    st.determinate = false;
    this.currentState = 'disconnected';
    this.applyIfActive(st);
  }

  setIdle() {
    this.currentState = 'connected';
    this.applyToDOM({
      jobId: this.currentJobId,
      status: 'connected',
      message: 'Ready',
      progress: 0,
      determinate: true,
      queuePosition: null,
    });
  }

  getCurrentJobId(): number | null {
    return this.currentJobId;
  }

  private ensure(jobId: number | null): JobUIState {
    const id = jobId ?? this.currentJobId ?? -1;
    let st = this.jobs.get(id);
    if (!st) {
      st = {
        jobId: id,
        status: 'executing',
        message: 'Running...',
        progress: null,
        determinate: false,
        queuePosition: null,
      };
      this.jobs.set(id, st);
    }
    return st;
  }

  private applyIfActive(st: JobUIState) {
    if (st.jobId === this.currentJobId || st.jobId === -1) {
      this.applyToDOM(st);
    }
  }

  private labelFor(status: ConnectionStatus): string {
    if (status === 'connected') return 'Ready';
    if (status === 'loading') return 'Starting...';
    if (status === 'executing') return 'Executing...';
    if (status === 'stopping') return 'Stopping...';
    return 'Disconnected';
  }

  private applyToDOM(st: JobUIState) {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
      indicator.className = `status-indicator ${st.status}`;
      const label = st.message || this.labelFor(st.status);
      indicator.setAttribute('title', label);
      indicator.setAttribute('aria-label', label);
      if (indicator.firstChild) {
        indicator.textContent = '';
      }
    }

    const progressRoot = document.getElementById('top-progress');
    const progressBar = document.getElementById('top-progress-bar');
    const progressText = document.getElementById('top-progress-text');

    if (progressRoot) {
      if (st.progress === 0 && st.determinate) {
        progressRoot.style.display = 'none';
      } else {
        progressRoot.style.display = 'block';
      }
    }

    if (progressText) {
      progressText.textContent = st.message;
    }

    if (progressBar) {
      if (st.determinate) {
        progressBar.classList.remove('indeterminate');
        (progressBar as HTMLElement).style.width = `${(st.progress ?? 0).toFixed(1)}%`;
      } else {
        progressBar.classList.add('indeterminate');
        (progressBar as HTMLElement).style.width = '100%';
      }
    }
  }
}
