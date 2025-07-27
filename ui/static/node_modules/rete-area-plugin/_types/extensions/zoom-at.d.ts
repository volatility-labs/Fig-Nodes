import { AreaPlugin } from '..';
import { NodeRef, SchemesWithSizes } from './shared/types';
/**
 * Zoom extension parameters
 */
export type Params = {
    /** Set gap between nodes and the viewport border */
    scale?: number;
};
/**
 * Zooms the area to fit the given nodes
 * @param plugin The area plugin
 * @param nodes The nodes to fit
 * @param params The zoom parameters
 */
export declare function zoomAt<Schemes extends SchemesWithSizes, K>(plugin: AreaPlugin<Schemes, K>, nodes: NodeRef<Schemes>[], params?: Params): Promise<void>;
//# sourceMappingURL=zoom-at.d.ts.map