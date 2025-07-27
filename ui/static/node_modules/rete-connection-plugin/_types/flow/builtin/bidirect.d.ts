import { ClassicScheme, SocketData } from '../../types';
import { Context, Flow, PickParams } from '../base';
import { State, StateContext } from '../utils';
/**
 * Bidirect flow params
 */
export declare type BidirectParams<Schemes extends ClassicScheme> = {
    /** If true, user can pick a pseudo-connection by clicking on socket, not only by pointerdown */
    pickByClick: boolean;
    /** Custom function to make connection */
    makeConnection: <K extends any[]>(from: SocketData, to: SocketData, context: Context<Schemes, K>) => boolean | undefined;
};
/**
 * Bidirect flow. User can pick a socket and connect it by releasing mouse button.
 * More simple than classic flow, but less functional (can't remove connection by clicking on input socket).
 */
export declare class BidirectFlow<Schemes extends ClassicScheme, K extends any[]> implements StateContext<Schemes, K>, Flow<Schemes, K> {
    currentState: State<Schemes, K>;
    constructor(params?: Partial<BidirectParams<Schemes>>);
    pick(params: PickParams, context: Context<Schemes, K>): Promise<void>;
    getPickedSocket(): SocketData | undefined;
    drop(context: Context<Schemes, K>): void;
    switchTo(state: State<Schemes, K>): void;
}
//# sourceMappingURL=bidirect.d.ts.map