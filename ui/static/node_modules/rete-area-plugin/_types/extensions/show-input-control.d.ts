import { BaseSchemes, ClassicPreset as Classic, GetSchemes } from 'rete';
import { BaseAreaPlugin } from '../base';
type Scheme = GetSchemes<Classic.Node, Classic.Connection<Classic.Node, Classic.Node>>;
type Visible<S extends Scheme> = (props: {
    hasAnyConnection: boolean;
    input: NonNullable<S['Node']['inputs'][string]>;
}) => boolean;
/**
 * Show input control extension. It will show the input's control when there is no connection and hide it when there is a connection.
 * @param area The base area plugin
 * @param visible The visible function
 * @listens connectioncreated
 * @listens connectionremoved
 */
export declare function showInputControl<S extends Scheme>(area: BaseAreaPlugin<BaseSchemes, any>, visible?: Visible<S>): void;
export {};
//# sourceMappingURL=show-input-control.d.ts.map