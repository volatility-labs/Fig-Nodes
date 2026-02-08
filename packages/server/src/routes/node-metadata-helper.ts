// routes/node-metadata-helper.ts
// Shared helper to extract node metadata from a node class.

export function getNodeMetadata(NodeClass: any) {
  const def = NodeClass.definition ?? {};

  const params = def.params?.length > 0 ? def.params : [];
  const defaults = def.defaults && Object.keys(def.defaults).length > 0
    ? def.defaults : {};

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
