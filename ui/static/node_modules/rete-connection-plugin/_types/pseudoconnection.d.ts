import { BaseArea, BaseAreaPlugin } from 'rete-area-plugin';
import { ClassicScheme, Position, SocketData } from './types';
/**
 * Create pseudoconnection. Used to trigger rendering of connection that is being created by user.
 * Has additional `isPseudo` property in payload.
 * @param extra Extra payload to add to connection
 */
export declare function createPseudoconnection<Schemes extends ClassicScheme, K>(extra?: Partial<Schemes['Connection']>): {
    isMounted(): boolean;
    mount: (areaPlugin: BaseAreaPlugin<Schemes, BaseArea<Schemes> | K>) => void;
    render(areaPlugin: BaseAreaPlugin<Schemes, BaseArea<Schemes> | K>, { x, y }: Position, data: SocketData): void;
    unmount: (areaPlugin: BaseAreaPlugin<Schemes, BaseArea<Schemes> | K>) => void;
};
//# sourceMappingURL=pseudoconnection.d.ts.map