import BaseCustomNode from './BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';

export default class OllamaChatViewerNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [360, 220];
        this.color = '#2c3e50';
        this.bgcolor = '#1b2836';
        this.displayResults = true;

        // Remove default params UI
        this.widgets = [];

        // Add control buttons
        this.addWidget('button', 'Copy', '', () => {
            if (this.displayText) navigator.clipboard.writeText(this.displayText);
        }, {});
        this.addWidget('button', 'Clear', '', () => {
            this.displayText = '';
            this.result = undefined;
            this.setDirtyCanvas(true, true);
        }, {});
    }

    onStreamUpdate(_data: any) {
        // Expect either { assistant_text } progressive or { assistant_message } final
        const text = _data?.assistant_text;
        const final = _data?.assistant_message;
        if (typeof text === 'string') {
            this.displayText = text;
        } else if (final && typeof final?.content === 'string') {
            this.displayText = final.content;
        }
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        // For non-stream payloads routed to viewer
        const textPref = result?.assistant_text;
        const msg = result?.assistant_message || result?.output || result;
        const text = typeof textPref === 'string' ? textPref : (typeof msg === 'string' ? msg : (msg?.content || JSON.stringify(msg, null, 2)));
        this.displayText = text || '';
        this.setDirtyCanvas(true, true);
    }
}


