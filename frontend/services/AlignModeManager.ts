import { LGraph } from '@fig-node/litegraph';
import { GraphAutoAlign } from './GraphAutoAlign';

export type AlignMode = 'align' | 'compact';

export class AlignModeManager {
    private static readonly STORAGE_KEY = 'fig-nodes:alignMode';
    private graph: LGraph;
    private currentMode: AlignMode;
    private readonly modeNames: AlignMode[] = ['align', 'compact'];

    constructor(graph: LGraph) {
        this.graph = graph;
        this.currentMode = 'align'; // Default to align
        this.initialize();
    }

    private initialize(): void {
        this.loadFromPreferences();
    }

    applyAlignMode(mode: AlignMode): void {
        this.currentMode = mode;
        this.executeAlign();
        this.updateButtonLabel();
        this.persistCurrentMode();
    }

    cycleAlignMode(): void {
        console.log('AlignModeManager: Cycling mode. Current:', this.currentMode);
        const currentIndex = this.modeNames.indexOf(this.currentMode);
        const nextIndex = (currentIndex + 1) % this.modeNames.length;
        const nextMode = this.modeNames[nextIndex];
        console.log('AlignModeManager: Next mode:', nextMode);
        if (nextMode) {
            this.applyAlignMode(nextMode);
        }
    }

    getCurrentMode(): AlignMode {
        return this.currentMode;
    }

    getModeName(mode?: AlignMode): string {
        const targetMode = mode ?? this.currentMode;
        return targetMode === 'compact' ? 'Compact' : 'Align';
    }

    private executeAlign(): void {
        if (this.currentMode === 'compact') {
            GraphAutoAlign.alignGraphCompact(this.graph);
        } else {
            GraphAutoAlign.alignGraph(this.graph);
        }
    }

    private updateButtonLabel(): void {
        const alignBtn = document.getElementById('auto-align-btn');
        if (alignBtn) {
            const modeName = this.getModeName();
            alignBtn.textContent = modeName;
            alignBtn.title = `Layout mode: ${modeName} (click to cycle)`;
        }
    }

    private persistCurrentMode(): void {
        try {
            localStorage.setItem(AlignModeManager.STORAGE_KEY, this.currentMode);
        } catch { /* ignore */ }
    }

    private loadFromPreferences(): void {
        try {
            const raw = localStorage.getItem(AlignModeManager.STORAGE_KEY);
            if (raw === 'align' || raw === 'compact') {
                this.currentMode = raw;
            }
        } catch { /* ignore */ }
    }
}

