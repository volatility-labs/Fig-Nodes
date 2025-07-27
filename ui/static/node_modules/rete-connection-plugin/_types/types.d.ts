import { ClassicPreset as Classic, GetSchemes } from 'rete';
import { Flow } from './flow';
export declare type Position = {
    x: number;
    y: number;
};
export declare type Side = 'input' | 'output';
export declare type SocketData = {
    element: HTMLElement;
    type: 'socket';
    nodeId: string;
    side: Side;
    key: string;
};
export declare type ConnectionExtra = {
    isPseudo?: boolean;
};
export declare type ClassicScheme = GetSchemes<Classic.Node, Classic.Connection<Classic.Node, Classic.Node> & ConnectionExtra>;
/**
 * Signal types produced by ConnectionPlugin instance
 * @priority 10
 */
export declare type Connection = {
    type: 'connectionpick';
    data: {
        socket: SocketData;
    };
} | {
    type: 'connectiondrop';
    data: {
        initial: SocketData;
        socket: SocketData | null;
        created: boolean;
    };
};
export declare type Preset<Schemes extends ClassicScheme> = (data: SocketData) => Flow<Schemes, any[]> | undefined;
//# sourceMappingURL=types.d.ts.map