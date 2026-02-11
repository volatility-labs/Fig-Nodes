// routes/logs.ts
// API endpoints for listing and reading execution log files.

import type { FastifyPluginAsync } from 'fastify';
import * as fs from 'fs';
import * as path from 'path';

const LOG_DIR = path.resolve(process.cwd(), 'logs');

export const logRoutes: FastifyPluginAsync = async (app) => {
  // List log files (newest first)
  app.get('/logs', async (_req, reply) => {
    if (!fs.existsSync(LOG_DIR)) {
      return reply.send({ files: [] });
    }

    const files = fs
      .readdirSync(LOG_DIR)
      .filter((f) => f.endsWith('.jsonl'))
      .sort()
      .reverse();

    return reply.send({ files });
  });

  // Read a single log file
  app.get<{ Params: { filename: string } }>('/logs/:filename', async (req, reply) => {
    const filename = path.basename(req.params.filename);

    if (!filename.endsWith('.jsonl')) {
      return reply.status(400).send({ error: 'Invalid file type' });
    }

    const filepath = path.join(LOG_DIR, filename);

    if (!fs.existsSync(filepath)) {
      return reply.status(404).send({ error: 'Log file not found' });
    }

    const content = fs.readFileSync(filepath, 'utf-8');
    const entries = content
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => {
        try {
          return JSON.parse(line);
        } catch {
          return null;
        }
      })
      .filter(Boolean);

    return reply.send({ filename, entries });
  });
};
