import { NodeEditor } from 'rete';
import { ClassicScheme, SocketData } from '../../../types';
/**
 * Remove existing connections if Port doesnt allow multiple connections
 */
export declare function syncConnections<Schemes extends ClassicScheme>(sockets: SocketData[], editor: NodeEditor<Schemes>): {
    commit(): void;
};
//# sourceMappingURL=sync-connections.d.ts.map