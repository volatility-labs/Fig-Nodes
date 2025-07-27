import { BaseAreaPlugin } from '../../base';
import { SchemesWithSizes } from './types';
export declare function getNodesRect<S extends SchemesWithSizes, K>(nodes: S['Node'][], views: BaseAreaPlugin<S, K>['nodeViews']): {
    position: import("../../types").Position;
    width: number;
    height: number;
}[];
//# sourceMappingURL=utils.d.ts.map