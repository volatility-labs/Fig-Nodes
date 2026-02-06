export interface SerialisedLink {
    id: number;
    origin_id: number;
    origin_slot: number;
    target_id: number;
    target_slot: number;
    type: unknown;
    parentId?: number;
}
export interface SerialisedNodeInput {
    name: string;
    type: unknown;
    linkIds?: number[];
}
export interface SerialisedNodeOutput {
    name: string;
    type: unknown;
    linkIds?: number[];
}
export interface SerialisedNode {
    id: number;
    type: string;
    title?: string;
    pos?: number[];
    size?: number[];
    flags?: Record<string, unknown>;
    order?: number;
    mode?: number;
    inputs?: SerialisedNodeInput[];
    outputs?: SerialisedNodeOutput[];
    properties?: Record<string, unknown>;
    shape?: unknown;
    boxcolor?: string;
    color?: string;
    bgcolor?: string;
    showAdvanced?: boolean;
    widgets_values?: unknown[];
}
export interface SerialisedGraphState {
    lastNodeId: number;
    lastLinkId: number;
    lastGroupId: number;
    lastRerouteId: number;
}
export interface SerialisableGraph {
    id?: string;
    revision?: number;
    version?: number;
    state?: SerialisedGraphState;
    nodes?: SerialisedNode[];
    links?: SerialisedLink[];
    floatingLinks?: SerialisedLink[];
    reroutes?: Array<Record<string, unknown>>;
    groups?: Array<Record<string, unknown>>;
    extra?: Record<string, unknown>;
    definitions?: Record<string, unknown>;
}
