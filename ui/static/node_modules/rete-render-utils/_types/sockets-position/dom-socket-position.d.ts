import { BaseSchemes } from 'rete';
import { Position, Side } from '../types';
import { BaseSocketPosition } from './base-socket-position';
/**
 * Props for `DOMSocketPosition` class.
 */
export declare type Props = {
    /**
     * Allows to customize the position of the socket. By default, the position is shifted by 12px on the x-axis relative to the center of the socket.
     * @param position Center position of the socket
     * @param nodeId Node ID
     * @param side Side of the socket, 'input' or 'output'
     * @param key Socket key
     * @returns Custom position of the socket
     */
    offset?: (position: Position, nodeId: string, side: Side, key: string) => Position;
};
/**
 * Class for socket position calculation based on DOM elements. It uses `getElementCenter` function to calculate the position.
 */
export declare class DOMSocketPosition<Schemes extends BaseSchemes, K> extends BaseSocketPosition<Schemes, K> {
    private props?;
    constructor(props?: Props | undefined);
    calculatePosition(nodeId: string, side: Side, key: string, element: HTMLElement): Promise<Position | null>;
}
/**
 * Wrapper function for `DOMSocketPosition` class.
 * @param props Props for `DOMSocketPosition` class
 */
export declare function getDOMSocketPosition<Schemes extends BaseSchemes, K>(props?: Props): DOMSocketPosition<Schemes, K>;
//# sourceMappingURL=dom-socket-position.d.ts.map