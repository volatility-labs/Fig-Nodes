
import BaseCustomNode from './BaseCustomNode';

export default class LoggingNodeUI extends BaseCustomNode {
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
        // If streaming-style payload, avoid replacing accumulated text
        if (result && (typeof result.delta === 'string' || (result.assistant_message && typeof result.assistant_message.content === 'string'))) {
            return;
        }
        const formatted = this.tryFormat(result);
        this.displayText = formatted;
        this.setDirtyCanvas(true, true);
    }

    onStreamUpdate(result: any) {
        // Handle both non-stream text and streaming chunks by appending
        const candidate = (result && typeof result.output !== 'undefined') ? result.output : result;
        let chunk: string = '';
        if (typeof candidate === 'string') {
            chunk = candidate;
        } else if (candidate && typeof (candidate as any).delta === 'string') {
            chunk = (candidate as any).delta;
        } else if (candidate && (candidate as any).assistant_message && typeof (candidate as any).assistant_message.content === 'string') {
            chunk = (candidate as any).assistant_message.content;
        } else {
            try { chunk = JSON.stringify(candidate); } catch { chunk = String(candidate ?? ''); }
        }

        // Append raw chunk first; then reformat depending on selected mode
        if (chunk) {
            const format = this.getSelectedFormat();
            if (format === 'json') {
                // Attempt to parse accumulated text as JSON for pretty view
                const accumulated = (this.displayText || '') + chunk;
                try {
                    const parsed = JSON.parse(accumulated);
                    this.displayText = JSON.stringify(parsed, null, 2);
                } catch {
                    // While not valid JSON yet, just append raw
                    this.displayText = accumulated;
                }
            } else if (format === 'auto') {
                const accumulated = (this.displayText || '') + chunk;
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
                // plain or markdown
                this.displayText = (this.displayText || '') + chunk;
            }
            this.setDirtyCanvas(true, true);
        }
    }
}