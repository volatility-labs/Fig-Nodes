import type { NodeRegistry } from '../types';
/**
 * Load all node classes from the specified directories.
 *
 * @param directories - List of directory paths to search for node modules
 * @returns Registry mapping node class names to their constructors
 */
export declare function loadNodes(directories: string[]): Promise<NodeRegistry>;
/**
 * Synchronously create an empty registry (for initialization).
 * Use loadNodes() to populate it asynchronously.
 */
export declare function createEmptyRegistry(): NodeRegistry;
/**
 * Get the global node registry.
 * Lazily initializes and caches the registry on first access.
 *
 * @param dirs - Optional list of directories to scan for node modules.
 *               If not provided, defaults to ['nodes'] resolved relative to core's source tree.
 */
export declare function getNodeRegistry(dirs?: string[]): Promise<NodeRegistry>;
/**
 * Reset the node registry (useful for testing).
 */
export declare function resetNodeRegistry(): void;
/**
 * Manually set the node registry (useful for testing or custom configurations).
 */
export declare function setNodeRegistry(registry: NodeRegistry): void;
