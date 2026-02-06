// src/types/graph.ts
// Simplified graph serialization types for the backend execution engine.
//
// These are intentionally looser versions of the canonical types defined in
// @fig-node/litegraph (packages/litegraph/src/types/serialisation.ts).
// Litegraph uses precise branded aliases (NodeId, LinkId, Point, etc.)
// whereas these use plain number/number[]/unknown for backend flexibility.
// A value conforming to litegraph's SerialisableGraph is assignable to this one.
export {};
