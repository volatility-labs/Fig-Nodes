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
        const msg = _data?.message;
        if (msg && typeof msg.content === 'string') {
            this.displayText = msg.content;
        }
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        // For non-stream payloads routed to viewer
        const msg = result?.message || result?.output || result;
        const text = (msg && typeof msg.content === 'string') ? msg.content : (typeof msg === 'string' ? msg : JSON.stringify(msg, null, 2));
        this.displayText = text || '';
        this.setDirtyCanvas(true, true);
    }
}


