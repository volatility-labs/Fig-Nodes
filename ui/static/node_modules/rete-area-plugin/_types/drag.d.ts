import { Position } from './types';
type Events = {
    start: (e: PointerEvent) => void;
    translate: (x: number, y: number, e: PointerEvent) => unknown;
    drag: (e: PointerEvent) => void;
};
type Guards = {
    down: (e: PointerEvent) => boolean;
    move: (e: PointerEvent) => boolean;
};
type DragConfig = {
    getCurrentPosition: () => Position;
    getZoom: () => number;
};
/**
 * Drag handler, used to handle dragging of the area and nodes. Can be extended to add custom behavior.
 */
export declare class Drag {
    private pointerStart?;
    private startPosition?;
    private pointerListener;
    protected config: DragConfig;
    protected events: Events;
    protected guards: Guards;
    constructor(guards?: Guards);
    initialize(element: HTMLElement, config: DragConfig, events: Events): void;
    private down;
    private move;
    private up;
    destroy(): void;
}
export {};
//# sourceMappingURL=drag.d.ts.map