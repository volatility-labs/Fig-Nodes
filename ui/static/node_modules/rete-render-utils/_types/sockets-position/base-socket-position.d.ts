import { BaseSchemes, NodeId, Scope } from 'rete';
import { BaseAreaPlugin } from 'rete-area-plugin';
import { ExpectArea2DExtra, Position, Side } from '../types';
import { EventEmitter } from '../utils';
import { SocketsPositionsStorage } from './storage';
import { OnChange, SocketPositionWatcher } from './types';
declare type ListenerData = {
    nodeId: string;
    side?: Side;
    key?: string;
};
/**
 * Abstract class for socket position calculation. It can be extended to implement custom socket position calculation.
 * @abstract
 * @listens render
 * @listens rendered
 * @listens unmount
 * @listens nodetranslated
 * @listens noderesized
 */
export declare abstract class BaseSocketPosition<Schemes extends BaseSchemes, K> implements SocketPositionWatcher<Scope<never, [K]>> {
    sockets: SocketsPositionsStorage;
    emitter: EventEmitter<ListenerData>;
    area: BaseAreaPlugin<Schemes, ExpectArea2DExtra<Schemes>> | null;
    /**
     * The method needs to be implemented that calculates the position of the socket.
     * @param nodeId Node ID
     * @param side Side of the socket, 'input' or 'output'
     * @param key Socket key
     * @param element Socket element
     */
    abstract calculatePosition(nodeId: string, side: Side, key: string, element: HTMLElement): Promise<Position | null>;
    /**
     * Attach the watcher to the area's child scope.
     * @param scope Scope of the watcher that should be a child of `BaseAreaPlugin`
     */
    attach(scope: Scope<never, [K]>): void;
    /**
     * Listen to socket position changes. Usually used by rendering plugins to update the start/end of the connection.
     * @internal
     * @param nodeId Node ID
     * @param side Side of the socket, 'input' or 'output'
     * @param key Socket key
     * @param change Callback function that is called when the socket position changes
     */
    listen(nodeId: NodeId, side: Side, key: string, change: OnChange): () => void;
}
export {};
//# sourceMappingURL=base-socket-position.d.ts.map