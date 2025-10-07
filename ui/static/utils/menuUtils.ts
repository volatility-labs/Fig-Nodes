import { IContextMenuValue, ContextMenu, LGraphCanvas, LGraph, LiteGraph } from '@comfyorg/litegraph';

export function getCanvasMenuOptions(canvas: LGraphCanvas, graph: LGraph, categorizedNodes: { [key: string]: string[] }): (e: MouseEvent) => void {
    return (e: MouseEvent) => {
        e.preventDefault();
        const options: IContextMenuValue[] = [
            {
                content: 'Add Node',
                has_submenu: true,
                callback: (value, options, event, parentMenu) => {
                    const submenu: IContextMenuValue[] = [];
                    for (const category in categorizedNodes) {
                        submenu.push({
                            content: category,
                            has_submenu: true,
                            callback: (value, options, event, parentMenu) => {
                                const subsubmenu: IContextMenuValue[] = [];
                                categorizedNodes[category].forEach((name: string) => {
                                    subsubmenu.push({
                                        content: name,
                                        callback: () => {
                                            const newNode = LiteGraph.createNode(name);
                                            if (newNode && event) {
                                                newNode.pos = canvas.convertEventToCanvasOffset(event as unknown as MouseEvent);
                                                graph.add(newNode as any);
                                            }
                                        }
                                    });
                                });
                                new ContextMenu(subsubmenu, { event, parentMenu });
                            }
                        });
                    }
                    new ContextMenu(submenu, { event, parentMenu });
                }
            },
            { content: 'Fit to window', callback: () => canvas.setZoom(1, [0, 0]) }
        ];
        new ContextMenu(options, { event: e, title: 'Canvas Menu' });
    };
}
