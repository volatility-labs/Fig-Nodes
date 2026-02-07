// types/node-metadata.ts
// Framework-agnostic node type metadata

import type { NodeUIConfig, ParamMeta } from '@fig-node/core';

/** Metadata about a node type, fetched from /api/v1/nodes */
export interface NodeTypeMetadata {
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  params: ParamMeta[];
  defaultParams: Record<string, unknown>;
  category: string;
  requiredKeys: string[];
  description: string;
  uiConfig: NodeUIConfig;
}

export type NodeMetadataMap = Record<string, NodeTypeMetadata>;
