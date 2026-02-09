// src/nodes/core/io/discord-output-node.ts

import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';
import { AssetClass, AssetSymbol } from './types';

/**
 * Sends a list of symbols to Discord via webhook.
 *
 * Input:
 * - symbols: AssetSymbol[] - The symbols to send to Discord
 *
 * Output:
 * - status: string - Success or error message
 *
 * Parameters:
 * - message_template: string - Template for the Discord message
 * - max_symbols_display: number - Maximum symbols to show (default: 50)
 */
export class DiscordOutput extends Node {
  static definition: NodeDefinition = {
    inputs: { symbols: port('AssetSymbolList') },
    outputs: { status: port('string') },
    requiredCredentials: [], // Optional key

    ui: {},

    params: [
      {
        name: 'message_template',
        type: 'text',
        default:
          '📊 **Trading Symbols Update**\n\n{symbol_list}\n\n*Total: {count} symbols*',
        label: 'Message Template',
        description:
          'Discord message template. Use {symbol_list} and {count} placeholders.',
      },
      {
        name: 'max_symbols_display',
        type: 'integer',
        default: 50,
        label: 'Max Symbols to Display',
        description: 'Maximum number of symbols to display in Discord (default: 50)',
      },
    ],

    category: NodeCategory.IO,
  };

  /**
   * Format symbols for Discord display.
   */
  private formatSymbolList(symbols: AssetSymbol[], maxDisplay: number): string {
    if (!symbols || symbols.length === 0) {
      return '*(No symbols)*';
    }

    // Group symbols by asset class
    const grouped: Record<string, string[]> = {};

    for (const symbol of symbols) {
      const assetClassName = symbol.assetClass;
      if (!grouped[assetClassName]) {
        grouped[assetClassName] = [];
      }
      grouped[assetClassName].push(symbol.ticker);
    }

    // Build formatted string with better styling
    const formattedParts: string[] = [];

    // Add emoji based on asset class
    const assetClassEmoji: Record<string, string> = {
      [AssetClass.STOCKS]: '📈',
      [AssetClass.CRYPTO]: '₿',
    };

    const sortedKeys = Object.keys(grouped).sort();
    for (const assetClass of sortedKeys) {
      const tickers = grouped[assetClass];
      if (!tickers) continue;

      // Sort tickers alphabetically
      tickers.sort();

      // Get emoji for this asset class
      const emoji = assetClassEmoji[assetClass] || '📊';

      // Format asset class name (capitalize first letter, lowercase rest)
      const displayName =
        assetClass.charAt(0).toUpperCase() + assetClass.slice(1).toLowerCase();

      // Check if we need to truncate
      if (tickers.length > maxDisplay) {
        const shownTickers = tickers.slice(0, maxDisplay);
        const remaining = tickers.length - maxDisplay;
        formattedParts.push(`${emoji} **${displayName}** (${tickers.length} total):`);
        formattedParts.push(shownTickers.map((t) => `\`${t}\``).join(', '));
        formattedParts.push(`*...and ${remaining} more*`);
      } else {
        formattedParts.push(`${emoji} **${displayName}** (${tickers.length}):`);
        formattedParts.push(tickers.map((t) => `\`${t}\``).join(', '));
      }

      formattedParts.push(''); // Empty line between groups
    }

    return formattedParts.join('\n').trim();
  }

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const symbols = (inputs.symbols as AssetSymbol[]) || [];

    console.log(
      `DiscordOutput: Starting execution with ${symbols.length} symbols`
    );

    if (symbols.length === 0) {
      console.log('DiscordOutput: No symbols provided, skipping Discord notification');
      this.progress(100.0, 'No symbols to send');
      return { status: 'Skipped (no symbols)' };
    }

    // Get Discord webhook URL from credentials (optional)
    const webhookUrl = this.hasCredentialProvider ? this.credentials.get('DISCORD_WEBHOOK_URL') : undefined;
    console.log(
      `DiscordOutput: Retrieved webhook URL from vault: ${webhookUrl ? 'Yes' : 'No'}`
    );

    if (!webhookUrl) {
      console.warn(
        'DiscordOutput: DISCORD_WEBHOOK_URL not set, skipping Discord notification'
      );
      this.progress(100.0, 'Webhook URL not configured');
      return { status: 'Skipped (no webhook URL configured)' };
    }

    // Get parameters
    const messageTemplateRaw = this.params.message_template;
    const messageTemplate =
      typeof messageTemplateRaw === 'string'
        ? messageTemplateRaw
        : '📊 **Trading Symbols Update**\n\n{symbol_list}\n\n*Total: {count} symbols*';

    const maxDisplayRaw = this.params.max_symbols_display;
    const maxDisplay =
      typeof maxDisplayRaw === 'number' ? maxDisplayRaw : 50;

    // Format symbol list
    const symbolListFormatted = this.formatSymbolList(symbols, maxDisplay);

    // Build message
    let messageContent = messageTemplate
      .replace('{symbol_list}', symbolListFormatted)
      .replace('{count}', String(symbols.length));

    // Discord has a 2000 character limit per message
    if (messageContent.length > 2000) {
      // Truncate and add warning
      messageContent =
        messageContent.slice(0, 1950) + '\n\n*...message truncated (too long)*';
    }

    // Send to Discord
    try {
      const payload = {
        content: messageContent,
        username: 'Fig Nodes Bot',
      };

      const response = await fetch(webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(10000),
      });

      if (response.status === 200 || response.status === 204) {
        console.log(
          `DiscordOutput: Successfully sent ${symbols.length} symbols to Discord`
        );
        return { status: `Success: ${symbols.length} symbols sent to Discord` };
      } else {
        const errorMsg = `Discord API error: ${response.status}`;
        console.error(`DiscordOutput: ${errorMsg}`);
        return { status: `Error: ${errorMsg}` };
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'TimeoutError') {
        console.error('DiscordOutput: Request to Discord timed out');
        return { status: 'Error: Request timed out' };
      }
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error(`DiscordOutput: Failed to send to Discord: ${errorMsg}`);
      return { status: `Error: ${errorMsg}` };
    }
  }
}
