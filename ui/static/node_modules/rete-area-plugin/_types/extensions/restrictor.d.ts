import { BaseSchemes } from 'rete';
import { AreaPlugin } from '..';
type ScaleRange = {
    min: number;
    max: number;
};
type TranslateRange = {
    left: number;
    top: number;
    right: number;
    bottom: number;
};
/**
 * Restrictor extension parameters
 */
export type Params = {
    /** The scaling range */
    scaling?: ScaleRange | (() => ScaleRange) | boolean;
    /** The translation range */
    translation?: TranslateRange | (() => TranslateRange) | boolean;
};
/**
 * Restrictor extension. Restricts the area zoom and position
 * @param plugin The area plugin
 * @param params The restrictor parameters
 * @listens zoom
 * @listens zoomed
 * @listens translated
 */
export declare function restrictor<Schemes extends BaseSchemes, K>(plugin: AreaPlugin<Schemes, K>, params?: Params): void;
export {};
//# sourceMappingURL=restrictor.d.ts.map