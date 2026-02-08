// server/src/credentials/env-credential-store.ts
// .env-backed credential store implementing CredentialProvider from core

import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
import type { CredentialProvider } from '@sosa/core';

/**
 * Singleton credential store backed by .env files and process.env.
 * Implements the read-only CredentialProvider interface from core,
 * plus write methods (set, unset, getAll) used by REST API routes.
 */
export class EnvCredentialStore implements CredentialProvider {
  private static instance: EnvCredentialStore | null = null;
  private keys: Map<string, string> = new Map();
  private dotenvPath: string;

  private constructor() {
    this.dotenvPath = this.resolveDotenvPath();
    this.loadKeys();
  }

  static getInstance(): EnvCredentialStore {
    if (!EnvCredentialStore.instance) {
      EnvCredentialStore.instance = new EnvCredentialStore();
    }
    return EnvCredentialStore.instance;
  }

  static reset(): void {
    EnvCredentialStore.instance = null;
  }

  // ── CredentialProvider interface ──

  get(key: string): string | undefined {
    return this.keys.get(key) ?? process.env[key];
  }

  has(key: string): boolean {
    return this.keys.has(key) || key in process.env;
  }

  // ── Write methods (server-only) ──

  set(key: string, value: string): void {
    this.keys.set(key, value);
    process.env[key] = value;

    const envPath = this.dotenvPath || '.env';
    this.updateEnvFile(envPath, key, value);
  }

  unset(key: string): void {
    this.keys.delete(key);
    delete process.env[key];

    if (this.dotenvPath && fs.existsSync(this.dotenvPath)) {
      this.removeFromEnvFile(this.dotenvPath, key);
    }
  }

  getAll(): Record<string, string> {
    const result: Record<string, string> = {};

    for (const [key, value] of this.keys) {
      result[key] = value;
    }

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

  // ── Private helpers ──

  private loadKeys(): void {
    if (this.dotenvPath && fs.existsSync(this.dotenvPath)) {
      dotenv.config({ path: this.dotenvPath, override: true });
    }

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

  private resolveDotenvPath(): string {
    let currentDir = process.cwd();
    const root = path.parse(currentDir).root;

    while (currentDir !== root) {
      const envPath = path.join(currentDir, '.env');
      if (fs.existsSync(envPath)) {
        return envPath;
      }
      currentDir = path.dirname(currentDir);
    }

    return path.join(process.cwd(), '.env');
  }

  private escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  private quoteEnvValue(value: string): string {
    if (/[\s"'\\]/.test(value) || value.includes('\n')) {
      return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
    }
    return value;
  }

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

/**
 * Convenience getter for the singleton credential store.
 */
export function getCredentialStore(): EnvCredentialStore {
  return EnvCredentialStore.getInstance();
}
