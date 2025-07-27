import { Position, Side } from '../types';
declare type SocketPayload = {
    element: HTMLElement;
    side: Side;
    key: string;
    nodeId: string;
    position: Position;
};
export declare class SocketsPositionsStorage {
    elements: Map<HTMLElement, SocketPayload[]>;
    getPosition(data: {
        nodeId: string;
        key: string;
        side: Side;
    }): Position | null;
    add(data: SocketPayload): void;
    remove(element: SocketPayload['element']): void;
    snapshot(): SocketPayload[];
}
export {};
//# sourceMappingURL=storage.d.ts.map