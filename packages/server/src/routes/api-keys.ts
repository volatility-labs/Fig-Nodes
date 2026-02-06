// API key management routes
import type { FastifyPluginAsync } from 'fastify';
import { getCredentialStore } from '../credentials/env-credential-store';

/**
 * Mask an API key for display (show first 4 and last 4 characters).
 */
function maskKey(value: string): string {
  if (value.length <= 8) {
    return '*'.repeat(value.length);
  }
  return `${value.slice(0, 4)}${'*'.repeat(value.length - 8)}${value.slice(-4)}`;
}

export const apiKeyRoutes: FastifyPluginAsync = async (fastify) => {
  const vault = getCredentialStore();

  /**
   * GET /api/v1/api_keys - List all API keys (masked)
   */
  fastify.get('/v1/api_keys', async () => {
    const allKeys = vault.getAll();
    const masked: Record<string, string> = {};

    for (const [key, value] of Object.entries(allKeys)) {
      masked[key] = maskKey(value);
    }

    return { keys: masked };
  });

  /**
   * POST /api/v1/api_keys - Set an API key
   * Body: { key: string, value: string }
   */
  fastify.post<{
    Body: { key: string; value: string };
  }>('/v1/api_keys', async (request, reply) => {
    const { key, value } = request.body;

    if (!key || typeof key !== 'string') {
      return reply.status(400).send({ error: 'Missing or invalid key' });
    }

    if (!value || typeof value !== 'string') {
      return reply.status(400).send({ error: 'Missing or invalid value' });
    }

    vault.set(key, value);

    return { success: true, key, masked: maskKey(value) };
  });

  /**
   * DELETE /api/v1/api_keys/:key - Delete an API key
   */
  fastify.delete<{
    Params: { key: string };
  }>('/v1/api_keys/:key', async (request, reply) => {
    const { key } = request.params;

    if (!vault.get(key)) {
      return reply.status(404).send({ error: `API key not found: ${key}` });
    }

    vault.unset(key);

    return { success: true, key };
  });
};
