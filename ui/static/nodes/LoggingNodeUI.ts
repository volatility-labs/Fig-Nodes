
import BaseCustomNode from './BaseCustomNode';

export default class LoggingNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);

        // Set larger size for displaying log data
        this.size = [400, 300];

        // Enable display for logging node specifically
        this.displayResults = true;

        // Add format selector widget
        this.addWidget('combo', 'Format', this.properties['format'] || 'auto', (value: string) => {
            this.properties['format'] = value;
        }, { values: ['auto', 'plain', 'json', 'markdown'] });
    }

    private getSelectedFormat(): 'auto' | 'plain' | 'json' | 'markdown' {
        const fmt = (this.properties && this.properties['format']) || 'auto';
        if (fmt === 'plain' || fmt === 'json' || fmt === 'markdown') return fmt;
        return 'auto';
    }

    private tryFormat(value: any): string {
        const format = this.getSelectedFormat();
        // Normalize candidate into a string or object first
        let candidate: any = value;
        if (candidate && typeof candidate === 'object' && 'output' in candidate) {
            candidate = (candidate as any).output;
        }

        // Helper to stringify objects consistently
        const stringifyPretty = (v: any) => {
            try { return JSON.stringify(v, null, 2); } catch { return String(v); }
        };

        if (value && typeof value === 'object' && 'role' in value && value.role === 'assistant' && 'content' in value) {
            let text = this.tryFormat(value.content);
            if ('thinking' in value && value.thinking) {
                text += '\n\nThinking: ' + this.tryFormat(value.thinking);
            }
            return text;
        }

        if (format === 'plain') {
            if (typeof candidate === 'string') return candidate;
            return stringifyPretty(candidate);
        }

        if (format === 'json') {
            if (typeof candidate === 'string') {
                try { return stringifyPretty(JSON.parse(candidate)); } catch { return candidate; }
            }
            return stringifyPretty(candidate);
        }

        if (format === 'markdown') {
            // We do not render markdown; we preserve text for canvas display.
            if (typeof candidate === 'string') return candidate;
            return stringifyPretty(candidate);
        }

        // auto: try JSON parse when string looks like JSON, else fallback to string/pretty
        if (typeof candidate === 'string') {
            const trimmed = candidate.trim();
            if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                try { return stringifyPretty(JSON.parse(candidate)); } catch { /* ignore */ }
            }
            return candidate;
        }
        return stringifyPretty(candidate);
    }

    reset() {
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        console.log('LoggingNodeUI.updateDisplay called with:', result);
        // If streaming-style payload, avoid replacing accumulated text
        if (result && (
            typeof (result as any).assistant_text === 'string' ||
            ((result as any).assistant_message && typeof (result as any).assistant_message.content === 'string') ||
            ((result as any).message && typeof (result as any).message.content === 'string')
        )) {
            return;
        }
        const formatted = this.tryFormat(result);
        this.displayText = formatted;
        console.log('displayText set to:', this.displayText);
        this.setDirtyCanvas(true, true);
    }

    onStreamUpdate(result: any) {
        let chunk: string = '';
        const format = this.getSelectedFormat();

        if (result.done) {
            // For final, format the full message
            this.displayText = this.tryFormat(result.message || result);
        } else {
            // Extract chunk for partial
            const candidate = (result.output || result);
            if (typeof candidate === 'string') {
                chunk = candidate;
            } else if (candidate && candidate.message && typeof candidate.message.content === 'string') {
                chunk = candidate.message.content;
            } else {
                try { chunk = JSON.stringify(candidate); } catch { chunk = String(candidate ?? ''); }
            }

            const prev = this.displayText || '';
            const accumulated = prev + chunk;

            if (prev && accumulated.startsWith(prev)) {
                this.displayText = accumulated;  // Replace with cumulative
            } else if (format === 'json') {
                try {
                    const parsed = JSON.parse(accumulated);
                    this.displayText = JSON.stringify(parsed, null, 2);
                } catch {
                    this.displayText = accumulated;
                }
            } else if (format === 'auto') {
                const trimmed = accumulated.trim();
                if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                    try {
                        const parsed = JSON.parse(accumulated);
                        this.displayText = JSON.stringify(parsed, null, 2);
                    } catch {
                        this.displayText = accumulated;
                    }
                } else {
                    this.displayText = accumulated;
                }
            } else {
                this.displayText = accumulated;
            }
        }
        this.setDirtyCanvas(true, true);
    }

    override onDrawForeground(ctx: CanvasRenderingContext2D) {
        console.log('LoggingNodeUI.onDrawForeground called, displayText:', this.displayText);
        console.log('Current size:', this.size);
        super.onDrawForeground(ctx);
        console.log('After super.onDrawForeground');
    }
}