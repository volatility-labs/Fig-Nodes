// types/nodes.ts
// Framework-agnostic node type metadata

import type { NodeUIConfig, ParamMeta, PortSpec } from '@fig-node/core';

/** Metadata about a node type, fetched from /api/v1/nodes */
export interface NodeTypeMetadata {
  inputs: Record<string, PortSpec>;
  outputs: Record<string, PortSpec>;
  params: ParamMeta[];
  defaultParams: Record<string, unknown>;
  category: string;
  requiredKeys: string[];
  description: string;
  uiConfig: NodeUIConfig;
}

export type NodeMetadataMap = Record<string, NodeTypeMetadata>;
