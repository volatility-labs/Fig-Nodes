// src/registry/node-registry.ts
// Dynamic node discovery and registration

import * as fs from 'fs';
import * as path from 'path';
import { pathToFileURL, fileURLToPath } from 'url';
import type { NodeRegistry, NodeConstructor } from '../types';
import { Base } from '../nodes/base/base-node';

// ESM equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Check if a class is a concrete (non-abstract) subclass of Base.
 */
function isConcreteNodeClass(obj: unknown): obj is typeof Base {
  if (typeof obj !== 'function') {
    return false;
  }

  // Check if it's a class that extends Base
  try {
    // Check prototype chain
    let proto = obj.prototype;
    while (proto) {
      if (proto.constructor === Base) {
        return false; // It's Base itself, not a subclass
      }
      if (proto instanceof Base || proto.constructor.name === 'Base') {
        // Check if it's abstract (has abstract methods not implemented)
        // In TypeScript, we can't truly check for abstract at runtime,
        // so we check if executeImpl is overridden using hasOwnProperty
        // We use 'as unknown as' to bypass protected access check at compile time
        const objProto = obj.prototype as unknown as Record<string, unknown>;
        const baseProto = Base.prototype as unknown as Record<string, unknown>;
        const hasExecuteImpl =
          objProto['executeImpl'] !== baseProto['executeImpl'] ||
          Object.prototype.hasOwnProperty.call(obj.prototype, 'executeImpl');
        return hasExecuteImpl;
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
      // Skip build output and dependency directories
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
 *
 * @param directories - List of directory paths to search for node modules
 * @returns Registry mapping node class names to their constructors
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
        // Convert to file URL for dynamic import
        const fileUrl = pathToFileURL(filePath).href;
        const module = await import(fileUrl);

        // Check all exports for node classes
        for (const [_exportName, exportValue] of Object.entries(module)) {
          if (isConcreteNodeClass(exportValue)) {
            // Use the class name as the registry key
            const className = (exportValue as { name: string }).name;
            if (className && className !== 'Base') {
              // Cast through unknown to bypass abstract constructor type check
              // We've already verified this is a concrete class via isConcreteNodeClass
              registry[className] = exportValue as unknown as NodeConstructor;

              // Validate that the node defines its own uiConfig
              const nodeClass = exportValue as typeof Base & { _isBaseUiConfig?: boolean };
              if (nodeClass._isBaseUiConfig === true) {
                console.warn(
                  `⚠️  Node "${className}" does not define its own uiConfig. ` +
                  `Please add a static uiConfig property for consistent UI behavior.`
                );
              }

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
 * Use loadNodes() to populate it asynchronously.
 */
export function createEmptyRegistry(): NodeRegistry {
  return {};
}

// Node registry singleton
let _nodeRegistry: NodeRegistry | null = null;
let _registryPromise: Promise<NodeRegistry> | null = null;

/**
 * Get the global node registry.
 * Lazily initializes and caches the registry on first access.
 *
 * @param dirs - Optional list of directories to scan for node modules.
 *               If not provided, defaults to ['nodes'] resolved relative to core's source tree.
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
