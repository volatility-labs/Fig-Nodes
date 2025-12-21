import { ServiceRegistry } from './ServiceRegistry';
import { ExecutionState } from '../types/websocketType';

export type ConnectionStatus = 'connected' | 'disconnected' | 'loading' | 'executing' | 'stopping';

// Map backend ExecutionState to frontend ConnectionStatus
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
        // When connected, show idle state with hidden progress bar
        const isIdle = status === 'connected';
        // Don't show "Initializing..." or "Connected" messages - keep status indicator empty when idle
        const displayMessage = (isIdle || status === 'loading') ? '' : (message ?? this.labelFor(status));
        this.applyToDOM({
            jobId: this.currentJobId,
            status,
            message: displayMessage,
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
        
        // Set progress based on state
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

    setStatus(jobId: number | null, message: string) {
        const st = this.ensure(jobId);
        st.message = message;
        if (/finished/i.test(message)) {
            st.status = 'connected';
            this.currentState = 'connected';
        } else if (/executing|starting/i.test(message)) {
            st.status = 'executing';
            this.currentState = 'executing';
        }
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

    finish(jobId: number | null) {
        const st = this.ensure(jobId);
        st.progress = 100;
        st.determinate = true;
        st.message = 'Finished';
        st.status = 'connected';
        this.currentState = 'connected';
        this.applyIfActive(st);
        setTimeout(() => this.setIdle(), 350);
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
            // Hide status indicator when idle or when message is empty
            const label = st.message || (st.status === 'connected' ? '' : this.labelFor(st.status));
            if (label) {
                indicator.textContent = label;
                indicator.style.display = 'inline-block';
            } else {
                indicator.textContent = '';
                indicator.style.display = 'none'; // Hide when no message
            }
            indicator.setAttribute('title', label || '');
            indicator.setAttribute('aria-label', label || '');
        }

        // Update polygon-status to show execution/scanning status
        // Note: Real-time/delayed data status takes priority and will override this
        const polygonStatus = document.getElementById('polygon-status');
        if (polygonStatus) {
            // Check if polygon-status is currently showing data status (real-time/delayed/etc)
            // Data status takes priority - don't override it with execution status
            const currentClass = polygonStatus.className;
            const isShowingDataStatus = currentClass.includes('real-time') || 
                                       currentClass.includes('delayed') || 
                                       currentClass.includes('market-closed') ||
                                       currentClass.includes('unknown');
            
            // Only show execution status if NOT showing data status
            if (!isShowingDataStatus) {
                if (st.status === 'executing' || st.status === 'loading') {
                    const statusClass = st.status === 'executing' ? 'executing' : 'scanning';
                    polygonStatus.className = `polygon-status ${statusClass}`;
                    const statusText = st.message || (st.status === 'executing' ? 'Running' : 'Scanning');
                    polygonStatus.textContent = statusText.toUpperCase();
                    polygonStatus.setAttribute('title', `Execution Status: ${statusText}`);
                } else if (st.status === 'stopping') {
                    polygonStatus.className = 'polygon-status delayed';
                    polygonStatus.textContent = 'Stopping';
                    polygonStatus.setAttribute('title', 'Execution Status: Stopping');
                } else {
                    // Reset to N/A when idle
                    polygonStatus.className = 'polygon-status polygon-status-na';
                    polygonStatus.textContent = 'N/A';
                    polygonStatus.setAttribute('title', 'Data Status: N/A');
                }
            }
            // If showing data status, keep it - don't override
        }

        const progressRoot = document.getElementById('top-progress');
        const progressBar = document.getElementById('top-progress-bar');
        const progressText = document.getElementById('top-progress-text');

        if (progressRoot) {
            // Hide progress bar when idle (progress=0, determinate=true)
            if (st.progress === 0 && st.determinate) {
                progressRoot.style.display = 'none';
            } else {
                progressRoot.style.display = 'block';
            }
        }

        if (progressText) {
            // Show execution status message (e.g., "Executing batch...")
            // Hide when idle or when message is generic "Executing..."
            if (st.message && st.message !== 'Executing...' && st.status !== 'connected') {
            progressText.textContent = st.message;
                progressText.style.display = 'block';
            } else {
                progressText.textContent = '';
                progressText.style.display = 'none';
            }
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

export function registerExecutionStatusService(registry: ServiceRegistry): ExecutionStatusService {
    const svc = new ExecutionStatusService();
    registry.register('statusService', svc);
    return svc;
}


