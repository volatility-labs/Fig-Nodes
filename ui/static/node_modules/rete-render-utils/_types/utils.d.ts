/**
 * Calculates the center coordinates of a child element relative to a parent element.
 * @async
 * @param child The child element whose center coordinates need to be calculated.
 * @param parent The parent element relative to which the child element's center is calculated.
 * @returns Position of the child element's center
 * @throws Error if the child element has a null offsetParent.
 */
export declare function getElementCenter(child: HTMLElement, parent: HTMLElement): Promise<{
    x: number;
    y: number;
}>;
export declare class EventEmitter<T> {
    listeners: Set<(data: T) => void>;
    emit(data: T): void;
    listen(handler: (data: T) => void): () => void;
}
//# sourceMappingURL=utils.d.ts.map