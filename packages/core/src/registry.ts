// src/registry.ts
// Dynamic node discovery, registration, and graph key extraction

import * as fs from 'fs';
import * as path from 'path';
import { pathToFileURL, fileURLToPath } from 'url';
import type { NodeRegistry, NodeConstructor } from './types.js';
import { Node } from './node.js';
import type { Graph } from './graph.js';
import { isRegisteredType } from './type-registry.js';
import type { PortSpec } from './types.js';

// ESM equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Check if a class is a concrete (non-abstract) subclass of Node.
 */
function isConcreteNodeClass(obj: unknown): obj is typeof Node {
  if (typeof obj !== 'function') {
    return false;
  }

  try {
    let proto = obj.prototype;
    while (proto) {
      if (proto.constructor === Node) {
        return false;
      }
      if (proto instanceof Node || proto.constructor.name === 'Node') {
        const objProto = obj.prototype as unknown as Record<string, unknown>;
        const baseProto = Node.prototype as unknown as Record<string, unknown>;
        const hasRun =
          objProto['run'] !== baseProto['run'] ||
          Object.prototype.hasOwnProperty.call(obj.prototype, 'run');
        return hasRun;
      }
      proto = Object.getPrototypeOf(proto);
    }
  } catch {
    return false;
  }

  return false;
}

/**
 * Recursively find all TypeScript/JavaScript files in a directory.
 */
function findNodeFiles(dir: string): string[] {
  const files: string[] = [];

  if (!fs.existsSync(dir)) {
    return files;
  }

  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === 'dist' || entry.name === 'node_modules') {
        continue;
      }
      files.push(...findNodeFiles(fullPath));
    } else if (
      entry.isFile() &&
      (entry.name.endsWith('.ts') || entry.name.endsWith('.js')) &&
      !entry.name.endsWith('.d.ts') &&
      !entry.name.endsWith('.test.ts') &&
      !entry.name.endsWith('.spec.ts') &&
      entry.name !== 'index.ts' &&
      entry.name !== 'index.js'
    ) {
      files.push(fullPath);
    }
  }

  return files;
}

/**
 * Load all node classes from the specified directories.
 */
export async function loadNodes(directories: string[]): Promise<NodeRegistry> {
  const registry: NodeRegistry = {};

  for (const dirPath of directories) {
    const absoluteDir = path.isAbsolute(dirPath)
      ? dirPath
      : path.resolve(__dirname, '..', dirPath);

    const files = findNodeFiles(absoluteDir);

    for (const filePath of files) {
      try {
        const fileUrl = pathToFileURL(filePath).href;
        const module = await import(fileUrl);

        for (const [_exportName, exportValue] of Object.entries(module)) {
          if (isConcreteNodeClass(exportValue)) {
            const className = (exportValue as { name: string }).name;
            if (className && className !== 'Node') {
              registry[className] = exportValue as unknown as NodeConstructor;
              console.log(`Registered node: ${className} from ${path.basename(filePath)}`);
            }
          }
        }
      } catch (error) {
        console.warn(`Failed to load node module ${filePath}: ${error}`);
      }
    }
  }

  return registry;
}

/**
 * Synchronously create an empty registry (for initialization).
 */
export function createEmptyRegistry(): NodeRegistry {
  return {};
}

// Node registry singleton
let _nodeRegistry: NodeRegistry | null = null;
let _registryPromise: Promise<NodeRegistry> | null = null;

/**
 * Get the global node registry.
 */
export async function getNodeRegistry(dirs?: string[]): Promise<NodeRegistry> {
  if (_nodeRegistry) {
    return _nodeRegistry;
  }

  if (_registryPromise) {
    return _registryPromise;
  }

  const directories = dirs ?? [path.resolve(__dirname, '..', 'nodes')];

  _registryPromise = loadNodes(directories).then((registry) => {
    _nodeRegistry = registry;
    return registry;
  });

  return _registryPromise;
}

/**
 * Reset the node registry (useful for testing).
 */
export function resetNodeRegistry(): void {
  _nodeRegistry = null;
  _registryPromise = null;
}

/**
 * Manually set the node registry (useful for testing or custom configurations).
 */
export function setNodeRegistry(registry: NodeRegistry): void {
  _nodeRegistry = registry;
  _registryPromise = null;
}

// ============ Node Definition Validation ============

/**
 * Validate all loaded node definitions against the type registry.
 * Returns an array of error messages for unknown port types.
 */
export function validateNodeDefinitions(registry: NodeRegistry): string[] {
  const errors: string[] = [];
  for (const [className, NodeClass] of Object.entries(registry)) {
    const def = (NodeClass as unknown as { definition?: { inputs?: Record<string, PortSpec>; outputs?: Record<string, PortSpec> } }).definition;
    if (!def) continue;
    for (const [portName, spec] of Object.entries(def.inputs ?? {})) {
      if (!isRegisteredType(spec.type)) {
        errors.push(`${className}: input '${portName}' uses unknown type '${spec.type}'`);
      }
    }
    for (const [portName, spec] of Object.entries(def.outputs ?? {})) {
      if (!isRegisteredType(spec.type)) {
        errors.push(`${className}: output '${portName}' uses unknown type '${spec.type}'`);
      }
    }
  }
  return errors;
}

// ============ Graph Keys ============

/**
 * Get all required API keys for a Graph by inspecting the
 * `definition.requiredCredentials` on each node class used in the graph.
 */
export function getRequiredKeysForDocument(
  doc: Graph,
  nodeRegistry: NodeRegistry
): string[] {
  const requiredKeys = new Set<string>();

  for (const node of Object.values(doc.nodes)) {
    const NodeClass = nodeRegistry[node.type];
    if (!NodeClass) continue;

    const keys = (NodeClass as unknown as { definition?: { requiredCredentials?: string[] } }).definition?.requiredCredentials ?? [];
    for (const key of keys) {
      if (typeof key === 'string' && key) {
        requiredKeys.add(key);
      }
    }
  }

  return Array.from(requiredKeys);
}
