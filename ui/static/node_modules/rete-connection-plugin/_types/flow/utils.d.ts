import { ClassicScheme, SocketData } from '../types';
import { Context, PickParams } from './base';
export interface StateContext<Schemes extends ClassicScheme, K extends any[]> {
    currentState: State<Schemes, K>;
    switchTo(state: State<Schemes, K>): void;
}
export declare abstract class State<Schemes extends ClassicScheme, K extends any[]> {
    context: StateContext<Schemes, K>;
    initial: SocketData | undefined;
    setContext(context: StateContext<Schemes, K>): void;
    abstract pick(params: PickParams, context: Context<Schemes, K>): Promise<void>;
    abstract drop(context: Context<Schemes, K>): void;
}
export declare function getSourceTarget(initial: SocketData, socket: SocketData): SocketData[] | undefined;
export declare function canMakeConnection(initial: SocketData, socket: SocketData): boolean;
export declare function makeConnection<Schemes extends ClassicScheme, K extends any[]>(initial: SocketData, socket: SocketData, context: Context<Schemes, K>): true | undefined;
//# sourceMappingURL=utils.d.ts.map