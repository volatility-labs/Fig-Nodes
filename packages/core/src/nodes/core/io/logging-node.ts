// Translated from: legacy/nodes/core/io/logging_node.py

import { Base } from '../../base/base-node';
import {
  NodeCategory,
  LLMChatMessage,
  OHLCVBar,
  AssetSymbol,
  getType,
  type ParamMeta,
  type NodeUIConfig,
  type NodeInputs,
  type NodeOutputs,
  type DefaultParams,
} from '../../../core/types';

// Type guards
function isDictWithKey(value: unknown, key: string): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && key in value;
}

function isListOfDicts(value: unknown): value is Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return false;
  return value.every((item) => typeof item === 'object' && item !== null);
}

function isLLMChatMessage(value: unknown): value is LLMChatMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    'role' in value &&
    'content' in value
  );
}

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

function isAssetSymbol(value: unknown): value is AssetSymbol {
  return value instanceof AssetSymbol;
}

function isAssetSymbolList(value: unknown): value is AssetSymbol[] {
  if (!Array.isArray(value)) return false;
  return value.length === 0 || value.every((item) => isAssetSymbol(item));
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

/**
 * Logging node that outputs data to console/logs with format options.
 */
export class Logging extends Base {
  static override inputs: Record<string, unknown> = {
    input: getType('any'),
  };

  static override outputs: Record<string, unknown> = {
    output: getType('string'),
  };

  static override CATEGORY = NodeCategory.IO;

  static override defaultParams: DefaultParams = {};

  static override paramsMeta: ParamMeta[] = [];

  static override uiConfig: NodeUIConfig = {
    size: [400, 300],
    resizable: true,
    displayResults: false,
    outputDisplay: {
      type: 'text-display-dom',
      bind: 'output',
      options: {
        placeholder: 'Logs appear here...',
        scrollable: true,
        streaming: true,
        formats: ['auto', 'json', 'plain', 'markdown'],
      },
    },
  };

  private lastContentLength = 0;

  constructor(
    id: number,
    params: Record<string, unknown>,
    graphContext: Record<string, unknown> = {}
  ) {
    super(id, params, graphContext);
  }

  private safePrint(message: string): void {
    try {
      console.log(`LoggingNode ${this.id}: ${message.trimEnd()}`);
    } catch {
      // Fallback if logging fails
      console.log(message.trimEnd());
    }
  }

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const value = inputs.input;

    // Handle missing or null input
    if (value === null || value === undefined) {
      this.safePrint('(no input)');
      return { output: '(no input)' };
    }

    let text: string;

    // Handle LLMChatMessage - extract only the content
    if (isLLMChatMessage(value) && isDictWithKey(value, 'content')) {
      const content = value.content;
      if (typeof content === 'string') {
        text = content;
        this.safePrint(text);
      } else {
        text = String(content);
        this.safePrint(text);
      }
    }
    // Handle streaming message format
    else if (
      isDictWithKey(value, 'message') &&
      typeof value.message === 'object' &&
      value.message !== null
    ) {
      const messageDict = value.message as Record<string, unknown>;
      if (messageDict.role === 'assistant' && typeof messageDict.content === 'string') {
        const content = messageDict.content;
        const isPartial = value.done !== true;
        const delta = content.slice(this.lastContentLength);

        if (delta) {
          process.stdout.write(delta);
        }

        if (!isPartial) {
          console.log(''); // Newline for final
          if ('thinking' in messageDict && typeof messageDict.thinking === 'string') {
            console.log('Thinking:', messageDict.thinking);
          }
          this.lastContentLength = 0;
        } else {
          this.lastContentLength = content.length;
        }

        text = content;
      } else {
        text = JSON.stringify(value);
        this.safePrint(text);
      }
    }
    // Handle AssetSymbol list
    else if (isAssetSymbolList(value)) {
      text = value.map((sym) => sym.toString()).join(', ');
      this.safePrint(text);
    }
    // Handle OHLCVBundle
    else if (isOHLCVBundle(value)) {
      const bundle = value;
      let totalBars = 0;
      for (const bars of Object.values(bundle)) {
        totalBars += bars.length;
      }
      const symbolCount = Object.keys(bundle).length;
      text = `OHLCVBundle data (${symbolCount} symbol(s), ${totalBars} total bars):\n`;

      let previewCount = 0;
      const entries = Object.entries(bundle).slice(0, 3);
      for (const [sym, bars] of entries) {
        if (Array.isArray(bars) && bars.length > 0) {
          const previewBars = Math.min(3, bars.length);
          text += `  ${sym} (${bars.length} bars):\n`;
          for (let i = 0; i < previewBars; i++) {
            const bar = bars[i];
            if (isOHLCVBar(bar)) {
              text += `    Bar ${i + 1}: ${bar.timestamp} O:${bar.open} H:${bar.high} L:${bar.low} C:${bar.close} V:${bar.volume}\n`;
            }
          }
          if (bars.length > previewBars) {
            text += `    ... and ${bars.length - previewBars} more bars\n`;
          }
          previewCount += bars.length;
        }
      }
      if (symbolCount > 3) {
        text += `  ... and ${symbolCount - 3} more symbols`;
      }

      // Only print in debug mode
      if (process.env.DEBUG_LOGGING === '1') {
        this.safePrint(text);
      }
    }
    // Handle legacy OHLCV format (list)
    else if (isListOfDicts(value) && value.length > 0 && isOHLCVBar(value[0])) {
      const previewCount = Math.min(10, value.length);
      text = `OHLCV data (${value.length} bars):\n`;
      for (let i = 0; i < previewCount; i++) {
        const bar = value[i];
        if (isOHLCVBar(bar)) {
          text += `Bar ${i + 1}: ${bar.timestamp} O:${bar.open} H:${bar.high} L:${bar.low} C:${bar.close} V:${bar.volume}\n`;
        }
      }
      if (value.length > previewCount) {
        text += `... and ${value.length - previewCount} more bars`;
      }

      // Only print in debug mode
      if (process.env.DEBUG_LOGGING === '1') {
        this.safePrint(text);
      }
    }
    // Fallback handling
    else {
      // Prefer message.content if present
      try {
        if (isDictWithKey(value, 'message') && typeof value.message === 'object') {
          const inner = value.message as Record<string, unknown>;
          if (typeof inner.content === 'string') {
            text = inner.content;
          } else {
            text = JSON.stringify(value);
          }
        } else {
          text = String(value);
        }
      } catch {
        text = String(value);
      }
      this.safePrint(text);
    }

    return { output: text };
  }
}
