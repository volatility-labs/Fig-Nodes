import { BaseSchemes, NodeEditor, Scope } from 'rete';
import { Connection, SocketData } from '../types';
export declare type Context<Schemes extends BaseSchemes, K extends any[]> = {
    editor: NodeEditor<Schemes>;
    scope: Scope<Connection, K>;
    socketsCache: Map<Element, SocketData>;
};
export declare type EventType = 'up' | 'down';
export declare type PickParams = {
    socket: SocketData;
    event: EventType;
};
export declare abstract class Flow<Schemes extends BaseSchemes, K extends any[]> {
    abstract pick(params: PickParams, context: Context<Schemes, K>): Promise<void>;
    abstract getPickedSocket(): SocketData | undefined;
    abstract drop(context: Context<Schemes, K>): void;
}
//# sourceMappingURL=base.d.ts.map