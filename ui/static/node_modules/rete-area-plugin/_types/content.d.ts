export declare class Content {
    private reordered;
    holder: HTMLElement;
    constructor(reordered: (target: HTMLElement) => Promise<unknown>);
    getPointerFrom(event: MouseEvent): {
        x: number;
        y: number;
    };
    add(element: HTMLElement): void;
    reorder(target: HTMLElement, next: ChildNode | null): Promise<void>;
    remove(element: HTMLElement): void;
}
//# sourceMappingURL=content.d.ts.map