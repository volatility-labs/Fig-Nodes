import { SocketData } from './types';
/**
 * @param elements list of Element returned by document.elementsFromPoint
 */
export declare function findSocket(socketsCache: WeakMap<Element, SocketData>, elements: Element[]): SocketData | undefined;
/**
 * Alternative to document.elementsFromPoint that traverses shadow roots
 * @param x x coordinate
 * @param y y coordinate
 * @param root root element to search in
 */
export declare function elementsFromPoint(x: number, y: number, root?: ShadowRoot | Document): Element[];
//# sourceMappingURL=utils.d.ts.map