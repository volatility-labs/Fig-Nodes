export type ParamScalar = string | number | boolean;
export type ParamValue = ParamScalar | null | ParamScalar[] | Record<string, unknown>;
export type ParamType = 'text' | 'textarea' | 'number' | 'integer' | 'int' | 'float' | 'combo' | 'boolean' | 'fileupload';
export interface ParamMeta {
    name: string;
    type?: ParamType;
    default?: ParamValue;
    options?: ParamScalar[] | Record<string, unknown>;
    min?: number;
    max?: number;
    step?: number;
    precision?: number;
    label?: string;
    unit?: string;
    description?: string;
}
export type DefaultParams = Record<string, ParamValue>;
export type NodeInputs = Record<string, unknown>;
export type NodeOutputs = Record<string, unknown>;
export type OutputDisplayType = 'text-display' | 'text-display-dom' | 'image-gallery' | 'image-viewer' | 'chart-preview' | 'note-display' | 'none';
export interface OutputDisplayConfig {
    type: OutputDisplayType;
    bind?: string;
    options?: OutputDisplayOptions;
}
export interface OutputDisplayOptions {
    placeholder?: string;
    scrollable?: boolean;
    copyButton?: boolean;
    formats?: ('auto' | 'json' | 'plain' | 'markdown')[];
    defaultFormat?: 'auto' | 'json' | 'plain' | 'markdown';
    streaming?: boolean;
    autoResize?: boolean;
    preserveAspectRatio?: boolean;
    gridLayout?: 'auto' | {
        cols: number;
        rows: number;
    };
    emptyText?: string;
    zoomable?: boolean;
    pannable?: boolean;
    infiniteScroll?: boolean;
    minZoom?: number;
    maxZoom?: number;
    chartType?: 'candlestick' | 'line';
    modalEnabled?: boolean;
    symbolSelector?: boolean;
    uniformColor?: string;
    orderLocked?: number;
    titleEditable?: boolean;
}
export type ResultDisplayMode = 'none' | 'json' | 'text' | 'summary' | 'custom';
export interface NodeAction {
    id: string;
    label: string;
    icon?: string;
    tooltip?: string;
}
export interface ResultFormatter {
    type: 'template' | 'fields';
    template?: string;
    fields?: string[];
    maxLines?: number;
}
export type BodyWidgetType = 'text' | 'textarea' | 'code' | 'json' | 'image' | 'chart' | 'table' | 'progress' | 'status' | 'custom';
export interface DataSource {
    endpoint: string;
    method?: 'GET' | 'POST';
    params?: Record<string, string>;
    headers?: Record<string, string>;
    refreshInterval?: number;
    transform?: string;
    targetParam?: string;
    valueField?: string;
    fallback?: unknown[];
}
export interface BodyWidget {
    type: BodyWidgetType;
    id: string;
    label?: string;
    bind?: string;
    dataSource?: DataSource;
    options?: BodyWidgetOptions;
    showIf?: string;
}
export interface BodyWidgetOptions {
    [key: string]: unknown;
    placeholder?: string;
    hideOnZoom?: boolean;
    zoomThreshold?: number;
    spellcheck?: boolean;
    rows?: number;
    readonly?: boolean;
    accept?: string;
    maxSize?: number;
    color?: string;
    height?: number;
    columns?: Array<{
        key: string;
        label: string;
        width?: number;
    }>;
    maxRows?: number;
    maxLines?: number;
    template?: string;
}
export interface ResultWidget {
    type: 'json' | 'text' | 'table' | 'image' | 'chart' | 'custom';
    bind?: string;
    maxHeight?: number;
    columns?: Array<{
        key: string;
        label: string;
        width?: number;
    }>;
    template?: string;
    chartConfig?: Record<string, unknown>;
}
export interface SlotConfig {
    color?: string;
    shape?: string;
    showType?: boolean;
}
export interface NodeUIConfig {
    size?: [number, number];
    resizable?: boolean;
    collapsable?: boolean;
    color?: string;
    bgcolor?: string;
    outputDisplay?: OutputDisplayConfig;
    body?: BodyWidget[];
    displayResults?: boolean;
    resultDisplay?: ResultDisplayMode;
    resultFormatter?: ResultFormatter;
    resultWidget?: ResultWidget;
    actions?: NodeAction[];
    inputSlots?: Record<string, SlotConfig>;
    outputSlots?: Record<string, SlotConfig>;
    inputTooltips?: Record<string, string>;
    outputTooltips?: Record<string, string>;
    dataSources?: Record<string, DataSource>;
    requiresCustomUI?: boolean;
}
