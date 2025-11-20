import BaseCustomNode from '../base/BaseCustomNode';

export default class LLMMessagesBuilderNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [340, 240];
        this.displayResults = true; // Display message summary
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


