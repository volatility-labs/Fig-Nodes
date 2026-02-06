// src/services/tools/registry.ts
// Translated from: services/tools/registry.py

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
