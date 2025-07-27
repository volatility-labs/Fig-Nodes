import { Position, Size } from './types';
type PointerHandler = (event: PointerEvent) => void;
type PointerListenerHandlers = {
    down: PointerHandler;
    move: PointerHandler;
    up: PointerHandler;
};
export type PointerListener = {
    destroy: () => void;
};
/**
 * listen to pointerdown, window's pointermove and pointerup events,
 * where last two not active before pointerdown triggered for performance reasons
 */
export declare function usePointerListener(element: HTMLElement, handlers: PointerListenerHandlers): PointerListener;
export declare function getBoundingBox(rects: ({
    position: Position;
} & Size)[]): {
    left: number;
    right: number;
    top: number;
    bottom: number;
    width: number;
    height: number;
    center: {
        x: number;
        y: number;
    };
};
export {};
//# sourceMappingURL=utils.d.ts.map