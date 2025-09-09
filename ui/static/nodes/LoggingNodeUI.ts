
import BaseCustomNode from './BaseCustomNode';

export default class LoggingNodeUI extends BaseCustomNode {
    reset() {
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        // If streaming-style payload, avoid replacing accumulated text
        if (result && (typeof result.delta === 'string' || (result.assistant_message && typeof result.assistant_message.content === 'string'))) {
            return;
        }
        super.updateDisplay(result);
    }

    onStreamUpdate(result: any) {
        // Handle both non-stream text and streaming chunks by appending
        const candidate = (result && typeof result.output !== 'undefined') ? result.output : result;
        let chunk: string;
        if (typeof candidate === 'string') {
            chunk = candidate;
        } else if (candidate && typeof candidate.delta === 'string') {
            chunk = candidate.delta;
        } else if (candidate && candidate.assistant_message && typeof candidate.assistant_message.content === 'string') {
            chunk = candidate.assistant_message.content;
        } else {
            chunk = typeof candidate === 'object' ? JSON.stringify(candidate) : String(candidate ?? '');
        }
        if (chunk) {
            this.displayText = (this.displayText || '') + chunk;
            this.setDirtyCanvas(true, true);
        }
    }
}