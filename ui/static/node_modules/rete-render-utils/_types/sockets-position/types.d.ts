import { NodeId } from 'rete';
import { Position, Side } from '../types';
export declare type OnChange = (data: Position) => void;
/**
 * Interface for socket position watcher.
 */
export declare type SocketPositionWatcher<ChildScope> = {
    /** Attach the watcher to the area's child scope. */
    attach(area: ChildScope): void;
    /**
     * Listen to the socket position changes.
     * @param nodeId Node ID
     * @param side Side of the socket, 'input' or 'output'
     * @param key Socket key
     * @param onChange Callback that is called when the socket position changes
     * @returns Function that removes the listener
     */
    listen(nodeId: NodeId, side: Side, key: string, onChange: OnChange): (() => void);
};
//# sourceMappingURL=types.d.ts.map