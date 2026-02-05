// src/services/tools/web-search.ts
// Translated from: services/tools/web_search.py

import {
  IToolHandler,
  ToolSchema,
  getCredentialFromContext,
  registerToolFactory,
} from './registry';

interface TavilySearchResult {
  results?: Array<{
    title?: string;
    url?: string;
    link?: string;
    content?: string;
    snippet?: string;
  }>;
  error?: string;
  message?: string;
}

interface WebSearchResult {
  results?: Array<{
    title: string;
    url: string;
    snippet: string;
  }>;
  used_provider?: string;
  error?: string;
  message?: string;
}

/**
 * Perform a web search using the Tavily API.
 */
async function tavilySearch(
  query: string,
  k: number,
  timeRange: string,
  _lang: string,
  topic: string,
  timeoutMs: number,
  apiKey: string
): Promise<WebSearchResult> {
  if (!apiKey) {
    return { error: 'missing_api_key', message: 'API key is required' };
  }

  const payload = {
    query,
    max_results: Math.max(1, Math.min(k || 5, 10)),
    search_depth: 'basic',
    time_range: timeRange || 'month',
    topic: topic || 'general',
    include_answer: false,
    include_raw_content: false,
    include_images: false,
  };

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiKey}`,
  };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = (await response.json()) as TavilySearchResult;

    const items: Array<{ title: string; url: string; snippet: string }> = [];
    const results = data.results || [];

    for (const item of results.slice(0, payload.max_results)) {
      items.push({
        title: item.title || '',
        url: item.url || item.link || '',
        snippet: item.content || item.snippet || '',
      });
    }

    return { results: items, used_provider: 'tavily' };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return { error: 'provider_error', message: errorMessage };
  }
}

/**
 * Web search tool implementation using Tavily API.
 */
export class WebSearchTool implements IToolHandler {
  readonly name = 'web_search';

  schema(): ToolSchema {
    return {
      type: 'function',
      function: {
        name: this.name,
        description: 'Search the web and return concise findings with sources.',
        parameters: {
          type: 'object',
          properties: {
            query: { type: 'string', description: 'Search query' },
            k: { type: 'integer', minimum: 1, maximum: 10, default: 5 },
            time_range: {
              type: 'string',
              enum: ['day', 'week', 'month', 'year'],
              default: 'month',
            },
            topic: {
              type: 'string',
              enum: ['general', 'news', 'finance'],
              default: 'general',
              description: 'Search topic category',
            },
            lang: {
              type: 'string',
              description: 'Language code like en, fr',
              default: 'en',
            },
          },
          required: ['query'],
        },
      },
    };
  }

  async execute(
    args: Record<string, unknown>,
    context: Record<string, unknown>
  ): Promise<WebSearchResult> {
    // Get API key from context
    const apiKey = getCredentialFromContext(context || {}, 'tavily_api_key');
    if (!apiKey) {
      return {
        error: 'missing_api_key',
        message: 'TAVILY_API_KEY credential not available',
      };
    }

    const query = (args || {}).query;
    if (typeof query !== 'string' || !query.trim()) {
      return {
        error: 'invalid_arguments',
        message: "'query' is required and must be a string",
      };
    }

    const k = typeof args.k === 'number' ? args.k : 5;
    const timeRange = typeof args.time_range === 'string' ? args.time_range : 'month';
    const lang = typeof args.lang === 'string' ? args.lang : 'en';
    const topic = typeof args.topic === 'string' ? args.topic : 'general';

    const timeoutMs =
      parseInt(process.env.WEB_SEARCH_TIMEOUT_S || '12', 10) * 1000 || 12000;

    return await tavilySearch(query, k, timeRange, lang, topic, timeoutMs, apiKey);
  }
}

// Register the web search tool factory
function createWebSearchTool(): WebSearchTool {
  return new WebSearchTool();
}

registerToolFactory('web_search', createWebSearchTool);

export { tavilySearch };
