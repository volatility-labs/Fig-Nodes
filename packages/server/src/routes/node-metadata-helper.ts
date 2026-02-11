// routes/node-metadata-helper.ts
// Shared helper to extract node metadata from a node class.

import { NodeCategory, type NodeConstructor, type NodeSchema, type ParamMeta, type NodeDefinition } from '@sosa/core';

interface NodeClassWithDefinition extends NodeConstructor {
  definition?: NodeDefinition;
  __doc?: string;
}

export function getNodeMetadata(NodeClass: NodeClassWithDefinition): NodeSchema {
  const def = NodeClass.definition ?? {};
  const params: ParamMeta[] = def.params?.length ? def.params : [];

  return {
    inputs: def.inputs ?? [],
    outputs: def.outputs ?? [],
    params,
    category: def.category ?? NodeCategory.BASE,
    requiredKeys: def.requiredCredentials ?? [],
    description: NodeClass.__doc ?? '',
    uiConfig: def.ui ?? {},
  };
}
