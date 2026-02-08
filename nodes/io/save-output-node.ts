import * as fs from 'fs';
import * as path from 'path';
import { randomUUID } from 'crypto';
import { Node, NodeCategory, port, type NodeDefinition } from '@fig-node/core';
import { AssetSymbol, type OHLCVBar } from '../market/types';

// Type guards
function isOHLCVBar(value: unknown): value is OHLCVBar {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    'timestamp' in v &&
    'open' in v &&
    'high' in v &&
    'low' in v &&
    'close' in v &&
    'volume' in v
  );
}

function isOHLCVBundle(value: unknown): value is Record<string, OHLCVBar[]> {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  const keys = Object.keys(v);
  if (keys.length === 0) return false;
  const firstKey = keys[0];
  if (!firstKey) return false;
  const firstValue = v[firstKey];
  if (!Array.isArray(firstValue)) return false;
  if (firstValue.length === 0) return true;
  return isOHLCVBar(firstValue[0]);
}

function isLLMChatMessage(value: unknown): value is { role: string; content: unknown } {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return 'role' in v && 'content' in v;
}

function isLLMToolSpec(value: unknown): value is { type: string; function: unknown } {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return v.type === 'function' && 'function' in v;
}

function isLLMChatMetrics(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return false;
  const metricKeys = [
    'total_duration',
    'load_duration',
    'prompt_eval_count',
    'prompt_eval_duration',
    'eval_count',
    'eval_duration',
    'error',
  ];
  const v = value as Record<string, unknown>;
  return metricKeys.some((key) => key in v);
}

function isLLMToolHistoryItem(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return 'call' in v && 'result' in v;
}

function isLLMThinkingHistoryItem(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return 'thinking' in v && 'iteration' in v;
}

interface SerializedValue {
  __type__: string;
  value?: unknown;
  data?: unknown;
  items?: SerializedValue[];
}

/**
 * Node to save node outputs to disk in the output folder.
 * The saved data is serialized in a format that preserves type information
 * so it can be read back by a corresponding load node.
 */
export class SaveOutput extends Node {
  static definition: NodeDefinition = {
    inputs: {
      data: port('any'),
    },

    outputs: {
      filepath: port('string'),
    },

    ui: {},

    category: NodeCategory.IO,

    params: [
      { name: 'filename', type: 'text', default: '' },
      { name: 'format', type: 'combo', default: 'json', options: ['json', 'jsonl'] },
      { name: 'overwrite', type: 'combo', default: false, options: [true, false] },
    ],
  };

  private serializeValue(value: unknown): SerializedValue {
    if (value === null || value === undefined) {
      return { __type__: 'None', value: null };
    }

    // Handle AssetSymbol
    if (value instanceof AssetSymbol) {
      return { __type__: 'AssetSymbol', data: value.toDict() };
    }

    // Handle arrays
    if (Array.isArray(value)) {
      return {
        __type__: 'list',
        items: value.map((item) => this.serializeValue(item)),
      };
    }

    // Handle objects
    if (typeof value === 'object' && value !== null) {
      const v = value as Record<string, unknown>;

      // Check various TypedDict types
      if (isOHLCVBar(v)) {
        return { __type__: 'OHLCVBar', data: v };
      } else if (isLLMChatMessage(v)) {
        return { __type__: 'LLMChatMessage', data: v };
      } else if (isLLMToolSpec(v)) {
        return { __type__: 'LLMToolSpec', data: v };
      } else if (isLLMChatMetrics(v)) {
        return { __type__: 'LLMChatMetrics', data: v };
      } else if (isLLMToolHistoryItem(v)) {
        return { __type__: 'LLMToolHistoryItem', data: v };
      } else if (isLLMThinkingHistoryItem(v)) {
        return { __type__: 'LLMThinkingHistoryItem', data: v };
      } else {
        // Regular dict
        const serializedData: Record<string, SerializedValue> = {};
        for (const [k, val] of Object.entries(v)) {
          serializedData[k] = this.serializeValue(val);
        }
        return { __type__: 'dict', data: serializedData };
      }
    }

    // Handle basic types
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return { __type__: typeof value, value };
    }

    // Fallback: convert to string
    try {
      return { __type__: 'string', value: String(value) };
    } catch {
      return { __type__: 'string', value: '[unserializable]' };
    }
  }

  private inferDataType(data: unknown): string {
    if (data instanceof AssetSymbol) {
      return 'AssetSymbol';
    } else if (Array.isArray(data)) {
      if (data.length > 0 && data[0] instanceof AssetSymbol) {
        return 'AssetSymbolList';
      } else if (data.length > 0 && typeof data[0] === 'object' && isOHLCVBar(data[0])) {
        return 'OHLCVBundle';
      } else {
        return 'List';
      }
    } else if (typeof data === 'object' && data !== null) {
      const d = data as Record<string, unknown>;
      if (isOHLCVBar(d)) {
        return 'OHLCVBar';
      } else if (isOHLCVBundle(d)) {
        return 'OHLCVBundle';
      } else if (isLLMChatMessage(d)) {
        return 'LLMChatMessage';
      } else {
        return 'Dict';
      }
    } else {
      return typeof data;
    }
  }

  private inferListItemType(data: unknown[]): string {
    if (data.length === 0) {
      return 'Any';
    }
    return this.inferDataType(data[0]);
  }

  private generateFilename(baseName: string, data: unknown, formatExt = '.json'): string {
    const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '_').slice(0, 15);

    // Determine type prefix
    let typePrefix: string;
    if (data instanceof AssetSymbol) {
      typePrefix = 'assetsymbol';
    } else if (Array.isArray(data)) {
      if (data.length > 0 && data[0] instanceof AssetSymbol) {
        typePrefix = 'assetsymbol_list';
      } else if (data.length > 0 && typeof data[0] === 'object' && isOHLCVBar(data[0])) {
        typePrefix = 'ohlcv_bundle';
      } else {
        typePrefix = 'list';
      }
    } else if (typeof data === 'object' && data !== null) {
      const d = data as Record<string, unknown>;
      if (isOHLCVBar(d)) {
        typePrefix = 'ohlcv_bar';
      } else if (isOHLCVBundle(d)) {
        typePrefix = 'ohlcv_bundle';
      } else if (isLLMChatMessage(d)) {
        typePrefix = 'llm_message';
      } else {
        typePrefix = 'dict';
      }
    } else if (typeof data === 'string') {
      typePrefix = 'text';
    } else {
      typePrefix = typeof data;
    }

    if (!baseName) {
      baseName = `${typePrefix}_${timestamp}_${randomUUID().slice(0, 8)}`;
    }

    // Ensure extension
    if (!baseName.endsWith(formatExt)) {
      baseName += formatExt;
    }

    return baseName;
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const data = inputs.data;
    if (data === null || data === undefined) {
      throw new Error('No data provided to save');
    }

    // Get parameters
    const filenameParam = this.params.filename;
    let baseFilename = filenameParam ? String(filenameParam).trim() : '';
    const formatType = String(this.params.format ?? 'json');
    const overwrite = Boolean(this.params.overwrite);
    const formatExt = formatType === 'jsonl' ? '.jsonl' : '.json';

    // Generate initial filename
    let filename = this.generateFilename(baseFilename, data, formatExt);

    // Create output directory if it doesn't exist
    const outputDir = path.join(process.cwd(), 'output');
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    let filepath = path.join(outputDir, filename);

    // If not overwrite, find unique name with counter
    if (!overwrite) {
      let counter = 1;
      const nameParts = filename.split(formatExt);
      while (fs.existsSync(filepath)) {
        filename = `${nameParts[0]}_${String(counter).padStart(3, '0')}${formatExt}`;
        filepath = path.join(outputDir, filename);
        counter++;
      }
    }

    // Serialize and save data
    try {
      if (formatType === 'jsonl' && Array.isArray(data)) {
        // JSON Lines format for lists
        const metadata = {
          __metadata__: {
            type: 'jsonl',
            item_type: this.inferListItemType(data),
            count: data.length,
            timestamp: new Date().toISOString(),
          },
        };

        const lines: string[] = [];
        lines.push(JSON.stringify(metadata));
        for (const item of data) {
          const serializedItem = this.serializeValue(item);
          lines.push(JSON.stringify(serializedItem));
        }

        fs.writeFileSync(filepath, lines.join('\n'), 'utf-8');
      } else {
        // Regular JSON format
        const serializedData = {
          __metadata__: {
            type: 'json',
            data_type: this.inferDataType(data),
            timestamp: new Date().toISOString(),
          },
          data: this.serializeValue(data),
        };

        fs.writeFileSync(filepath, JSON.stringify(serializedData, null, 2), 'utf-8');
      }
    } catch (error) {
      throw new Error(`Failed to save to ${filepath}: ${error}`);
    }

    return { filepath };
  }
}
