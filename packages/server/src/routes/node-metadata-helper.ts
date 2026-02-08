// routes/node-metadata-helper.ts
// Shared helper to extract node metadata from a node class.

export function getNodeMetadata(NodeClass: any) {
  const def = NodeClass.definition ?? {};

  const params = def.params?.length > 0 ? def.params : [];

  // Derive defaultParams from params[].default (single source of truth)
  const defaults: Record<string, unknown> = {};
  for (const p of params) {
    if (p.default !== undefined) defaults[p.name] = p.default;
  }

  return {
    inputs: def.inputs ?? {},
    outputs: def.outputs ?? {},
    params,
    defaultParams: defaults,
    category: def.category ?? 'base',
    requiredKeys: def.requiredCredentials ?? [],
    description: NodeClass.__doc ?? '',
    uiConfig: def.ui ?? {},
  };
}
