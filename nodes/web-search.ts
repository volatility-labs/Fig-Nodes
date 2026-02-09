// src/services/tools/web-search.ts
// Translated from: services/tools/web_search.py

// --- Inlined from tool-registry.ts ---

/**
 * A lightweight registry for LLM tool schemas and async handlers.
 * Handlers should be async callables that accept arguments and context.
 */

export interface ToolSchema {
  type: string;
  function: {
    name: string;
    description: string;
    parameters: {
      type: string;
      properties: Record<string, unknown>;
      required?: string[];
    };
  };
}

export type ToolHandler = (
  args: Record<string, unknown>,
  context: Record<string, unknown>
) => Promise<unknown>;

export type ToolFactory = () => IToolHandler;

export type ToolCredentialProvider = () => string;

// Internal registries
const _TOOL_SCHEMAS: Map<string, ToolSchema> = new Map();
const _TOOL_HANDLERS: Map<string, ToolHandler> = new Map();
const _TOOL_FACTORIES: Map<string, ToolFactory> = new Map();
const _CREDENTIAL_PROVIDERS: Map<string, ToolCredentialProvider> = new Map();

/**
 * Register a tool schema.
 */
export function registerToolSchema(name: string, schema: ToolSchema): void {
  if (!name) {
    throw new Error('Tool schema name must be a non-empty string');
  }
  if (!schema) {
    throw new Error('Tool schema must be a non-empty object');
  }
  _TOOL_SCHEMAS.set(name, schema);
}

/**
 * Get a tool schema by name.
 */
export function getToolSchema(name: string): ToolSchema | undefined {
  return _TOOL_SCHEMAS.get(name);
}

/**
 * List all registered tool names.
 */
export function listToolNames(): string[] {
  return Array.from(_TOOL_SCHEMAS.keys()).sort();
}

/**
 * List all registered tool schemas.
 */
export function listToolSchemas(): ToolSchema[] {
  return listToolNames()
    .map((name) => _TOOL_SCHEMAS.get(name))
    .filter((schema): schema is ToolSchema => schema !== undefined);
}

/**
 * Register a tool handler.
 */
export function registerToolHandler(name: string, handler: ToolHandler): void {
  if (!name) {
    throw new Error('Tool handler name must be a non-empty string');
  }
  if (typeof handler !== 'function') {
    throw new Error('Tool handler must be callable');
  }
  _TOOL_HANDLERS.set(name, handler);
}

/**
 * Get a tool handler by name.
 */
export function getToolHandler(name: string): ToolHandler | undefined {
  return _TOOL_HANDLERS.get(name);
}

/**
 * Register a tool factory that can create tool instances with credentials.
 */
export function registerToolFactory(name: string, factory: ToolFactory): void {
  if (!name) {
    throw new Error('Tool factory name must be a non-empty string');
  }
  if (typeof factory !== 'function') {
    throw new Error('Tool factory must be callable');
  }
  _TOOL_FACTORIES.set(name, factory);

  // Also register/update the schema from the tool instance
  try {
    const toolInstance = factory();
    registerToolSchema(name, toolInstance.schema());
  } catch {
    // If factory fails, keep existing schema
  }

  // Create a handler that instantiates the tool and calls execute
  const factoryHandler: ToolHandler = async (args, context) => {
    const tool = factory();
    return await tool.execute(args, context);
  };

  registerToolHandler(name, factoryHandler);
}

/**
 * Get a tool factory by name.
 */
export function getToolFactory(name: string): ToolFactory | undefined {
  return _TOOL_FACTORIES.get(name);
}

/**
 * Register a credential provider for a specific credential type.
 */
export function registerToolCredentialProvider(name: string, provider: ToolCredentialProvider): void {
  if (!name) {
    throw new Error('Credential provider name must be a non-empty string');
  }
  if (typeof provider !== 'function') {
    throw new Error('Credential provider must be callable');
  }
  _CREDENTIAL_PROVIDERS.set(name, provider);
}

/**
 * Get a credential provider by name.
 */
export function getToolCredentialProvider(name: string): ToolCredentialProvider | undefined {
  return _CREDENTIAL_PROVIDERS.get(name);
}

/**
 * Get a credential value from registered providers.
 */
export function getCredential(name: string): string | undefined {
  const provider = getToolCredentialProvider(name);
  if (provider) {
    try {
      return provider();
    } catch {
      return undefined;
    }
  }
  return undefined;
}

/**
 * Get all registered credential providers.
 */
export function getAllToolCredentialProviders(): Record<string, ToolCredentialProvider> {
  const result: Record<string, ToolCredentialProvider> = {};
  _CREDENTIAL_PROVIDERS.forEach((provider, name) => {
    result[name] = provider;
  });
  return result;
}

/**
 * Standard interface for implementing tool providers.
 */
export interface IToolHandler {
  readonly name: string;
  schema(): ToolSchema;
  execute(args: Record<string, unknown>, context: Record<string, unknown>): Promise<unknown>;
}

/**
 * Helper function for tools to get credentials from execution context.
 */
export function getCredentialFromContext(
  context: Record<string, unknown>,
  credentialName: string
): string | undefined {
  const credentials = context.credentials;
  if (credentials && typeof credentials === 'object' && credentialName in credentials) {
    const credentialsObj = credentials as Record<string, unknown>;
    const provider = credentialsObj[credentialName];
    if (typeof provider === 'function') {
      try {
        return (provider as ToolCredentialProvider)();
      } catch {
        return undefined;
      }
    }
    if (typeof provider === 'string') {
      return provider;
    }
  }
  return undefined;
}

/**
 * Registers both schema and handler from a ToolHandler implementation.
 */
export function registerToolObject(tool: IToolHandler): void {
  registerToolSchema(tool.name, tool.schema());

  const boundHandler: ToolHandler = async (args, context) => {
    return await tool.execute(args, context);
  };

  registerToolHandler(tool.name, boundHandler);
}

// Default web_search tool schema
const DEFAULT_WEB_SEARCH_SCHEMA: ToolSchema = {
  type: 'function',
  function: {
    name: 'web_search',
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

async function defaultUnimplementedHandler(
  args: Record<string, unknown>,
  _context: Record<string, unknown>
): Promise<unknown> {
  // Provide a deterministic, JSON-serializable error payload for unconfigured tools
  return {
    error: 'handler_not_configured',
    message: 'No handler is registered for this tool on the server.',
    arguments_echo: args,
  };
}

// Register defaults at import time
registerToolSchema('web_search', DEFAULT_WEB_SEARCH_SCHEMA);
registerToolHandler('web_search', defaultUnimplementedHandler);

// --- End inlined tool-registry.ts ---

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
