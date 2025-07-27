import { Drag } from './drag';
import { Position, Size } from './types';
export type NodeTranslateEventParams = {
    position: Position;
    previous: Position;
};
export type NodeResizeEventParams = {
    size: Size;
};
type Events = {
    picked: () => void;
    translated: (params: NodeTranslateEventParams) => Promise<unknown>;
    dragged: () => void;
    contextmenu: (event: MouseEvent) => void;
    resized: (params: NodeResizeEventParams) => Promise<unknown>;
};
type Guards = {
    resize: (params: NodeResizeEventParams) => Promise<unknown>;
    translate: (params: NodeTranslateEventParams) => Promise<unknown>;
};
export declare class NodeView {
    private getZoom;
    private events;
    private guards;
    element: HTMLElement;
    position: Position;
    dragHandler: Drag;
    constructor(getZoom: () => number, events: Events, guards: Guards);
    translate: (x: number, y: number) => Promise<boolean>;
    resize: (width: number, height: number) => Promise<boolean>;
    destroy(): void;
}
export {};
//# sourceMappingURL=node-view.d.ts.map