import { BaseSchemes } from 'rete';
import { BaseAreaPlugin } from '../base';
/**
 * Snap grid extension parameters
 */
export type Params = {
    /** The grid size */
    size?: number;
    /** Whether to snap on node drag */
    dynamic?: boolean;
};
/**
 * Snap grid extension
 * @param base The base area plugin
 * @param params The snap parameters
 * @listens nodetranslate
 * @listens nodedragged
 */
export declare function snapGrid<Schemes extends BaseSchemes, K>(base: BaseAreaPlugin<Schemes, K>, params?: Params): void;
//# sourceMappingURL=snap.d.ts.map