import BaseCustomNode from '../base/BaseCustomNode';

export default class LLMMessagesBuilderNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [340, 160];
        this.color = '#243447';
        this.bgcolor = '#0e1621';

        // Do not render long result text; show short summary instead

        // Convenience buttons
        this.addWidget('button', 'Clear', '', () => {
            this.displayText = '';
            this.setDirtyCanvas(true, true);
        }, {});
        this.addWidget('button', 'Copy Summary', '', () => {
            if (this.displayText) navigator.clipboard.writeText(this.displayText);
        }, {});
    }

    updateDisplay(result: any) {
        // Expect { messages: [...] }
        const msgs = result?.messages;
        if (!Array.isArray(msgs)) {
            this.displayText = '';
            this.setDirtyCanvas(true, true);
            return;
        }
        // Summarize messages for compact display
        const summary = msgs.map((m: any, i: number) => {
            const role = m?.role || 'unknown';
            let content = m?.content;
            if (typeof content !== 'string') content = JSON.stringify(content);
            const trimmed = (content || '').replace(/\s+/g, ' ').slice(0, 60);
            return `${i + 1}. ${role}: ${trimmed}${(content || '').length > 60 ? '…' : ''}`;
        }).join('\n');
        this.displayText = summary;
        this.setDirtyCanvas(true, true);
    }
}


