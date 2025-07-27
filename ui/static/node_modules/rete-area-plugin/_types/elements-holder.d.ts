export declare class ElementsHolder<E extends HTMLElement, Ctx extends {
    type: string;
    element: E;
    payload?: {
        id: string;
    };
}> {
    views: WeakMap<E, Ctx>;
    viewsElements: Map<`${string}_${string}`, E>;
    set(context: Ctx): void;
    get(type: string, id: string): Ctx | undefined;
    delete(element: E): void;
}
//# sourceMappingURL=elements-holder.d.ts.map