
import BaseCustomNode from '../base/BaseCustomNode';

export default class LoggingNodeUI extends BaseCustomNode {
    private copyButton: any = null;
    private copyFeedbackTimeout: number | null = null;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Set larger size for displaying log data
        this.size = [400, 300];

        // Enable native canvas text rendering
        this.displayResults = true;

        // Add copy button widget
        this.copyButton = this.addWidget('button', '📋 Copy Log', '', () => {
            this.copyLogToClipboard();
        }, {});
    }

    private copyLogToClipboard() {
        const textToCopy = this.displayText || '';
        if (!textToCopy.trim()) {
            this.showCopyFeedback('No content to copy', false);
            return;
        }

        navigator.clipboard.writeText(textToCopy).then(() => {
            this.showCopyFeedback('Copied to clipboard!', true);
        }).catch((err) => {
            console.error('Failed to copy text: ', err);
            this.showCopyFeedback('Copy failed', false);
        });
    }

    private showCopyFeedback(message: string, success: boolean) {
        if (this.copyButton) {
            const originalText = this.copyButton.name;
            this.copyButton.name = success ? '✅ ' + message : '❌ ' + message;

            // Clear any existing timeout
            if (this.copyFeedbackTimeout) {
                clearTimeout(this.copyFeedbackTimeout);
            }

            // Reset button text after 2 seconds
            this.copyFeedbackTimeout = window.setTimeout(() => {
                this.copyButton.name = originalText;
                this.copyFeedbackTimeout = null;
                this.setDirtyCanvas(true, true);
            }, 2000);

            this.setDirtyCanvas(true, true);
        }
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
            candidate = (candidate as { output: any }).output;
        }

        // Helper to stringify objects consistently
        const stringifyPretty = (v: any) => {
            try { return JSON.stringify(v, null, 2); } catch { return String(v); }
        };

        // Handle LLMChatMessage - extract only the content
        if (value && typeof value === 'object' && 'role' in value && 'content' in value) {
            // This is an LLMChatMessage - extract only the content
            let text = this.tryFormat(value.content);
            // Optionally include thinking if present and format is not 'plain'
            if ('thinking' in value && value.thinking && format !== 'plain') {
                text += '\n\nThinking: ' + this.tryFormat(value.thinking);
            }
            return text;
        }

        // Handle simple objects with content property (like streaming messages)
        if (value && typeof value === 'object' && 'content' in value && Object.keys(value).length === 1) {
            return this.tryFormat(value.content);
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
            typeof (result as { assistant_text?: string }).assistant_text === 'string' ||
            ((result as { assistant_message?: { content?: string } }).assistant_message && typeof (result as { assistant_message: { content: string } }).assistant_message.content === 'string') ||
            ((result as { message?: { content?: string } }).message && typeof (result as { message: { content: string } }).message.content === 'string')
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

            // If chunk starts with prev, it's cumulative; otherwise replace
            if (prev && chunk.startsWith(prev)) {
                this.displayText = chunk;  // Replace with cumulative chunk
            } else {
                // Not cumulative, so use the chunk as-is (possibly formatted)
                if (format === 'json') {
                    try {
                        const parsed = JSON.parse(chunk);
                        this.displayText = JSON.stringify(parsed, null, 2);
                    } catch {
                        this.displayText = chunk;
                    }
                } else if (format === 'auto') {
                    const trimmed = chunk.trim();
                    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                        try {
                            const parsed = JSON.parse(chunk);
                            this.displayText = JSON.stringify(parsed, null, 2);
                        } catch {
                            this.displayText = chunk;
                        }
                    } else {
                        this.displayText = chunk;
                    }
                } else {
                    this.displayText = chunk;
                }
            }
        }
        this.setDirtyCanvas(true, true);
    }

    // Clean up timeouts when node is destroyed
    onRemoved() {
        if (this.copyFeedbackTimeout) {
            clearTimeout(this.copyFeedbackTimeout);
            this.copyFeedbackTimeout = null;
        }
        super.onRemoved?.();
    }
}