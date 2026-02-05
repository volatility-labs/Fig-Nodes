// backend/core/api-key-vault.ts
// Translated from: core/api_key_vault.py

import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
import type { NodeRegistry, SerialisableGraph } from './types';

/**
 * Singleton class for managing API keys stored in environment variables.
 */
export class APIKeyVault {
  private static instance: APIKeyVault | null = null;
  private keys: Map<string, string> = new Map();
  private dotenvPath: string;

  private constructor() {
    this.dotenvPath = this.resolveDotenvPath();
    this.loadKeys();
  }

  /**
   * Get the singleton instance.
   */
  static getInstance(): APIKeyVault {
    if (!APIKeyVault.instance) {
      APIKeyVault.instance = new APIKeyVault();
    }
    return APIKeyVault.instance;
  }

  /**
   * Reset the singleton instance (useful for testing).
   */
  static reset(): void {
    APIKeyVault.instance = null;
  }

  /**
   * Load environment variables and cache relevant keys.
   */
  private loadKeys(): void {
    // Load .env file
    if (this.dotenvPath && fs.existsSync(this.dotenvPath)) {
      dotenv.config({ path: this.dotenvPath, override: true });
    }

    // Cache all keys that start with typical API key prefixes
    const prefixes = ['API', 'KEY', 'TOKEN', 'SECRET'];
    const knownKeys = ['POLYGON_API_KEY', 'TAVILY_API_KEY', 'OLLAMA_API_KEY', 'OPENROUTER_API_KEY'];

    for (const [key, value] of Object.entries(process.env)) {
      if (value === undefined) continue;

      const upperKey = key.toUpperCase();
      const hasPrefix = prefixes.some((prefix) => upperKey.includes(prefix));
      const isKnownKey = knownKeys.includes(key);

      if (hasPrefix || isKnownKey) {
        this.keys.set(key, value);
      }
    }
  }

  /**
   * Get an API key by name.
   */
  get(key: string): string | undefined {
    return this.keys.get(key) ?? process.env[key];
  }

  /**
   * Set an API key and persist it to the .env file.
   */
  set(key: string, value: string): void {
    this.keys.set(key, value);
    process.env[key] = value;

    // Persist to .env file
    const envPath = this.dotenvPath || '.env';
    this.updateEnvFile(envPath, key, value);
  }

  /**
   * Get all API keys.
   */
  getAll(): Record<string, string> {
    const result: Record<string, string> = {};

    // Include cached keys
    for (const [key, value] of this.keys) {
      result[key] = value;
    }

    // Include any new keys from environment
    const prefixes = ['API', 'KEY', 'TOKEN', 'SECRET'];
    const knownKeys = ['POLYGON_API_KEY', 'TAVILY_API_KEY', 'OLLAMA_API_KEY', 'OPENROUTER_API_KEY'];

    for (const [key, value] of Object.entries(process.env)) {
      if (value === undefined) continue;

      const upperKey = key.toUpperCase();
      const hasPrefix = prefixes.some((prefix) => upperKey.includes(prefix));
      const isKnownKey = knownKeys.includes(key);

      if (hasPrefix || isKnownKey) {
        result[key] = value;
      }
    }

    return result;
  }

  /**
   * Get all required API keys for a given graph.
   */
  getRequiredForGraph(graph: SerialisableGraph, nodeRegistry: NodeRegistry): string[] {
    const requiredKeys = new Set<string>();

    const nodes = graph.nodes ?? [];
    for (const nodeData of nodes) {
      const nodeType = nodeData.type;
      const NodeClass = nodeRegistry[nodeType];

      if (!NodeClass) {
        continue;
      }

      // Check for required_keys static property on the node class
      const keys = (NodeClass as unknown as { required_keys?: string[] }).required_keys ?? [];
      for (const key of keys) {
        if (typeof key === 'string' && key) {
          requiredKeys.add(key);
        }
      }
    }

    return Array.from(requiredKeys);
  }

  /**
   * Remove an API key from cache, environment, and .env file.
   */
  unset(key: string): void {
    this.keys.delete(key);
    delete process.env[key];

    if (this.dotenvPath && fs.existsSync(this.dotenvPath)) {
      this.removeFromEnvFile(this.dotenvPath, key);
    }
  }

  /**
   * Find the .env file using standard resolution.
   */
  private resolveDotenvPath(): string {
    // Search upward from current directory
    let currentDir = process.cwd();
    const root = path.parse(currentDir).root;

    while (currentDir !== root) {
      const envPath = path.join(currentDir, '.env');
      if (fs.existsSync(envPath)) {
        return envPath;
      }
      currentDir = path.dirname(currentDir);
    }

    // Default to .env in current directory
    return path.join(process.cwd(), '.env');
  }

  /**
   * Escape special regex characters in a string.
   */
  private escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * Quote a value for .env file if it contains special characters.
   */
  private quoteEnvValue(value: string): string {
    // If value contains spaces, quotes, or newlines, wrap in double quotes and escape internal quotes
    if (/[\s"'\\]/.test(value) || value.includes('\n')) {
      return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
    }
    return value;
  }

  /**
   * Update or add a key in the .env file.
   */
  private updateEnvFile(filePath: string, key: string, value: string): void {
    let content = '';

    if (fs.existsSync(filePath)) {
      content = fs.readFileSync(filePath, 'utf-8');
    }

    const lines = content.split('\n');
    const keyRegex = new RegExp(`^${this.escapeRegex(key)}=`);
    const quotedValue = this.quoteEnvValue(value);
    let found = false;

    const newLines = lines.map((line) => {
      if (keyRegex.test(line)) {
        found = true;
        return `${key}=${quotedValue}`;
      }
      return line;
    });

    if (!found) {
      newLines.push(`${key}=${quotedValue}`);
    }

    fs.writeFileSync(filePath, newLines.join('\n'));
  }

  /**
   * Remove a key from the .env file.
   */
  private removeFromEnvFile(filePath: string, key: string): void {
    if (!fs.existsSync(filePath)) {
      return;
    }

    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');
    const keyRegex = new RegExp(`^${this.escapeRegex(key)}=`);

    const newLines = lines.filter((line) => !keyRegex.test(line));

    fs.writeFileSync(filePath, newLines.join('\n'));
  }
}

// Export singleton getter for convenience
export function getVault(): APIKeyVault {
  return APIKeyVault.getInstance();
}
