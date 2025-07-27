import { BaseSchemes } from 'rete';
import { BaseAreaPlugin } from '../base';
import { NodeRef } from './shared/types';
/**
 * Get the bounding box of the given nodes
 * @param plugin The area plugin
 * @param nodes The nodes to get the bounding box of
 * @returns The bounding box
 */
export declare function getBoundingBox<Schemes extends BaseSchemes, K>(plugin: BaseAreaPlugin<Schemes, K>, nodes: NodeRef<Schemes>[]): {
    left: number;
    right: number;
    top: number;
    bottom: number;
    width: number;
    height: number;
    center: {
        x: number;
        y: number;
    };
};
//# sourceMappingURL=bounding-box.d.ts.map