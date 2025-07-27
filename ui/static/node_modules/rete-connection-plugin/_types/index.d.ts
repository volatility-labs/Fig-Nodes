import { Scope } from 'rete';
import { RenderSignal } from 'rete-area-plugin';
import { EventType } from './flow/base';
import { ClassicScheme, Connection, Position, Preset, Side } from './types';
export * from './flow';
export * as Presets from './presets';
export { createPseudoconnection } from './pseudoconnection';
export type { Connection, ConnectionExtra, Preset, Side, SocketData } from './types';
declare type Requires = {
    type: 'pointermove';
    data: {
        position: Position;
        event: PointerEvent;
    };
} | {
    type: 'pointerup';
    data: {
        position: Position;
        event: PointerEvent;
    };
} | RenderSignal<'socket', {
    nodeId: string;
    side: Side;
    key: string;
}> | {
    type: 'unmount';
    data: {
        element: HTMLElement;
    };
};
/**
 * Connection plugin. Responsible for user interaction with connections (creation, deletion)
 * @priority 9
 * @emits connectionpick
 * @emits connectiondrop
 * @listens pointermove
 * @listens pointerup
 * @listens render
 * @listens unmount
 */
export declare class ConnectionPlugin<Schemes extends ClassicScheme, K = Requires> extends Scope<Connection, [Requires | K]> {
    presets: Preset<Schemes>[];
    private areaPlugin;
    private editor;
    private currentFlow;
    private preudoconnection;
    private socketsCache;
    constructor();
    /**
     * Add preset to the plugin
     * @param preset Preset to add
     */
    addPreset(preset: Preset<Schemes>): void;
    private findPreset;
    update(): void;
    /**
     * Drop pseudo-connection if exists
     * @emits connectiondrop
     */
    drop(): void;
    pick(event: PointerEvent, type: EventType): Promise<void>;
    setParent(scope: Scope<Requires | K>): void;
}
//# sourceMappingURL=index.d.ts.map