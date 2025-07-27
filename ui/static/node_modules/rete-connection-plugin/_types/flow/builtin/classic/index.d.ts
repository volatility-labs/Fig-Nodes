import { ClassicScheme, SocketData } from '../../../types';
import { Context, Flow, PickParams } from '../../base';
import { State, StateContext } from '../../utils';
/**
 * Classic flow params
 */
export declare type ClassicParams<Schemes extends ClassicScheme> = {
    /** Custom function to check if connection can be made */
    canMakeConnection: (from: SocketData, to: SocketData) => boolean | undefined;
    /** Custom function to make connection */
    makeConnection: <K extends any[]>(from: SocketData, to: SocketData, context: Context<Schemes, K>) => boolean | undefined;
};
/**
 * Classic flow. User can pick/click a socket and connect it by releasing/clicking on another socket.
 * If connection already exists and user clicks on input socket, connection will be removed.
 */
export declare class ClassicFlow<Schemes extends ClassicScheme, K extends any[]> implements StateContext<Schemes, K>, Flow<Schemes, K> {
    currentState: State<Schemes, K>;
    constructor(params?: Partial<ClassicParams<Schemes>>);
    pick(params: PickParams, context: Context<Schemes, K>): Promise<void>;
    getPickedSocket(): SocketData | undefined;
    switchTo(state: State<Schemes, K>): void;
    drop(context: Context<Schemes, K>): void;
}
//# sourceMappingURL=index.d.ts.map