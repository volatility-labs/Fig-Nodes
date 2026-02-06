/**
 * Detect the type of a value and return a canonical type name.
 */
export declare function detectType(value: unknown): string;
/**
 * Infer a high-level data type name for metadata purposes.
 */
export declare function inferDataType(data: unknown): string;
/**
 * Parse a TypeScript type representation into a structured format.
 */
export declare function parseTypeString(typeStr: string): Record<string, unknown>;
