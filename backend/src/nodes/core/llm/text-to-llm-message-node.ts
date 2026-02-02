// src/nodes/core/llm/text-to-llm-message-node.ts
// Translated from: nodes/core/llm/text_to_llm_message_node.py

import { Base } from '../../base/base-node';
import { NodeCategory, getType } from '../../../core/types';
import type {
  NodeInputs,
  NodeOutputs,
  ParamMeta,
  DefaultParams,
} from '../../../core/types';

type RoleType = 'user' | 'assistant' | 'system' | 'tool';
type FormatType = 'json' | 'readable' | 'compact';

/**
 * Adapter node: wraps generic input data into an LLMChatMessage.
 *
 * Can handle various input types including strings, numbers, dictionaries, lists,
 * and structured data like OHLCV bars from Polygon API.
 *
 * Inputs:
 * - data: Any (required) - Generic input that will be converted to text
 *
 * Params:
 * - role: str in {"user", "assistant", "system", "tool"}
 * - format: str - How to format structured data ("json", "readable", "compact")
 *
 * Outputs:
 * - message: LLMChatMessage
 */
export class TextToLLMMessage extends Base {
  static override inputs: Record<string, unknown> = {
    data: Object, // Any type
  };

  static override outputs: Record<string, unknown> = {
    message: getType('LLMChatMessage'),
  };

  static override defaultParams: DefaultParams = {
    role: 'user',
    format: 'readable',
  };

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'role',
      type: 'combo',
      default: 'user',
      options: ['user', 'assistant', 'system', 'tool'],
    },
    {
      name: 'format',
      type: 'combo',
      default: 'readable',
      options: ['json', 'readable', 'compact'],
    },
  ];

  static override CATEGORY = NodeCategory.LLM;

  private isOhlcvBar(data: unknown): data is Record<string, unknown> {
    if (typeof data !== 'object' || data === null) return false;
    const obj = data as Record<string, unknown>;
    return ['timestamp', 'open', 'high', 'low', 'close', 'volume'].every(
      (k) => k in obj
    );
  }

  private isChatMessage(data: unknown): data is Record<string, unknown> {
    if (typeof data !== 'object' || data === null) return false;
    const obj = data as Record<string, unknown>;
    return (
      'role' in obj &&
      'content' in obj &&
      ['system', 'user', 'assistant', 'tool'].includes(String(obj.role))
    );
  }

  private isIndicatorResult(data: unknown): data is Record<string, unknown> {
    if (typeof data !== 'object' || data === null) return false;
    const obj = data as Record<string, unknown>;
    return 'indicator_type' in obj && 'values' in obj;
  }

  private formatOhlcvBar(bar: Record<string, unknown>): string {
    let timestamp = bar.timestamp ?? 'N/A';
    if (typeof timestamp === 'number' && timestamp > 1e10) {
      const dt = new Date(timestamp);
      timestamp = dt.toISOString().replace('T', ' ').substring(0, 19);
    }
    return (
      `${timestamp} | O:${bar.open ?? 'N/A'} ` +
      `H:${bar.high ?? 'N/A'} L:${bar.low ?? 'N/A'} ` +
      `C:${bar.close ?? 'N/A'} V:${bar.volume ?? 'N/A'}`
    );
  }

  private formatChatMessage(msg: Record<string, unknown>): string {
    const role = msg.role ?? 'unknown';
    let content = msg.content ?? '';
    if (typeof content === 'object') {
      content = JSON.stringify(content, null, 2);
    }
    const parts = [`Role: ${role}`];
    if ('thinking' in msg) {
      parts.push(`Thinking: ${msg.thinking}`);
    }
    if ('tool_calls' in msg && Array.isArray(msg.tool_calls)) {
      parts.push(`Tool calls: ${msg.tool_calls.length}`);
    }
    parts.push(`Content: ${content}`);
    return parts.join('\n');
  }

  private formatIndicatorResult(result: Record<string, unknown>): string {
    const indicatorType = result.indicator_type ?? 'unknown';
    const values = result.values ?? {};
    const lines = [`Indicator: ${indicatorType}`];
    if (typeof values === 'object' && values !== null) {
      const valObj = values as Record<string, unknown>;
      if ('single' in valObj) {
        lines.push(`Value: ${valObj.single}`);
      }
      if ('lines' in valObj) {
        lines.push(`Lines: ${valObj.lines}`);
      }
    }
    return lines.join('\n');
  }

  private formatOhlcvData(ohlcvList: Record<string, unknown>[]): string {
    if (!ohlcvList.length) {
      return 'No OHLCV data available';
    }

    const lines = ['OHLCV Data:'];
    for (let i = 0; i < Math.min(ohlcvList.length, 20); i++) {
      lines.push(`  ${i + 1}. ${this.formatOhlcvBar(ohlcvList[i])}`);
    }

    if (ohlcvList.length > 20) {
      lines.push(`  ... and ${ohlcvList.length - 20} more bars`);
    }

    return lines.join('\n');
  }

  private formatDictItem(item: Record<string, unknown>): string {
    if (!item || Object.keys(item).length === 0) {
      return '{}';
    }

    const pairs: string[] = [];
    const entries = Object.entries(item).slice(0, 3);
    for (const [key, value] of entries) {
      if (
        (typeof value === 'string' ||
          typeof value === 'number' ||
          typeof value === 'boolean') &&
        String(value).length < 50
      ) {
        pairs.push(`${key}=${value}`);
      } else {
        pairs.push(`${key}=(${typeof value})`);
      }
    }

    let result = pairs.join(', ');
    if (Object.keys(item).length > 3) {
      result += ` (+${Object.keys(item).length - 3} more)`;
    }
    return result;
  }

  private formatAsJson(data: unknown, options?: { indent?: number; separators?: [string, string] }): string {
    try {
      if (options?.separators) {
        return JSON.stringify(data);
      }
      return JSON.stringify(data, null, options?.indent ?? 0);
    } catch {
      return String(data);
    }
  }

  private formatDictReadable(data: Record<string, unknown>): string {
    if (this.isOhlcvBar(data)) {
      return this.formatOhlcvBar(data);
    }
    if (this.isChatMessage(data)) {
      return this.formatChatMessage(data);
    }
    if (this.isIndicatorResult(data)) {
      return this.formatIndicatorResult(data);
    }

    // Special case: dict containing ohlcv list (Polygon API format)
    if ('ohlcv' in data && Array.isArray(data.ohlcv)) {
      return this.formatOhlcvData(data.ohlcv as Record<string, unknown>[]);
    }

    // Generic dict formatting
    return this.formatGenericDict(data);
  }

  private formatListReadable(data: unknown[]): string {
    if (!data.length) {
      return '[]';
    }

    // Check first item to determine list structure
    if (typeof data[0] === 'object' && data[0] !== null) {
      if (this.isOhlcvBar(data[0])) {
        return this.formatOhlcvList(data as Record<string, unknown>[]);
      }
      if (data.length <= 10) {
        return this.formatDictList(data as Record<string, unknown>[]);
      }
    }

    // Default to JSON for other lists
    return this.formatAsJson(data, { indent: 2 });
  }

  private formatOhlcvList(data: Record<string, unknown>[]): string {
    const lines: string[] = [];
    for (let i = 0; i < Math.min(data.length, 20); i++) {
      lines.push(`${i + 1}. ${this.formatOhlcvBar(data[i])}`);
    }
    if (data.length > 20) {
      lines.push(`... and ${data.length - 20} more`);
    }
    return lines.join('\n');
  }

  private formatDictList(data: Record<string, unknown>[]): string {
    const lines: string[] = [];
    for (let i = 0; i < data.length; i++) {
      lines.push(`${i + 1}. ${this.formatDictItem(data[i])}`);
    }
    return lines.join('\n');
  }

  private formatGenericDict(data: Record<string, unknown>): string {
    const lines: string[] = [];
    for (const [key, value] of Object.entries(data)) {
      if (Array.isArray(value) && value.length > 0) {
        const isListOfDicts =
          typeof value[0] === 'object' && value[0] !== null;
        if (isListOfDicts) {
          lines.push(`${key}:`);
          let count = 0;
          for (const item of value) {
            if (count >= 100) break;
            if (typeof item === 'object' && item !== null) {
              lines.push(
                `  ${count + 1}. ${this.formatDictItem(item as Record<string, unknown>)}`
              );
              count++;
            }
          }
          if (value.length > 100) {
            lines.push(`  ... and ${value.length - 100} more items`);
          }
        } else {
          lines.push(`${key}: ${value}`);
        }
      } else {
        lines.push(`${key}: ${value}`);
      }
    }
    return lines.join('\n');
  }

  private formatData(data: unknown, formatType: FormatType): string {
    if (data === null || data === undefined) {
      return '';
    }

    if (typeof data === 'string') {
      return data;
    }

    if (
      typeof data === 'number' ||
      typeof data === 'boolean'
    ) {
      return String(data);
    }

    // JSON and compact formats don't need type-specific handling
    if (formatType === 'json') {
      return this.formatAsJson(data, { indent: 2 });
    }
    if (formatType === 'compact') {
      return this.formatAsJson(data, { separators: [',', ':'] });
    }

    // Readable format - handle based on data structure
    if (typeof data === 'object' && !Array.isArray(data)) {
      return this.formatDictReadable(data as Record<string, unknown>);
    }
    if (Array.isArray(data)) {
      return this.formatListReadable(data);
    }

    return String(data);
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const data = inputs.data;
    let role = String(this.params.role ?? 'user').toLowerCase() as RoleType;
    let formatType = String(this.params.format ?? 'readable').toLowerCase() as FormatType;

    if (!['user', 'assistant', 'system', 'tool'].includes(role)) {
      role = 'user';
    }

    if (!['json', 'readable', 'compact'].includes(formatType)) {
      formatType = 'readable';
    }

    // Convert data to string representation
    const content = this.formatData(data, formatType);

    const msg = { role, content };
    return { message: msg };
  }
}
