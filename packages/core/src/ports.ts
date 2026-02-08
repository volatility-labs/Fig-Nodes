// src/ports.ts
// Port and parameter types used by every node and the engine

export type ParamScalar = string | number | boolean;
export type ParamValue = ParamScalar | null | ParamScalar[] | Record<string, unknown>;
export type ParamType = 'text' | 'textarea' | 'number' | 'integer' | 'int' | 'float' | 'combo' | 'boolean' | 'fileupload';

export interface ParamMeta {
  name: string;
  type?: ParamType;
  default?: ParamValue;
  options?: ParamScalar[] | Record<string, unknown>;
  min?: number;
  max?: number;
  step?: number;
  precision?: number;
  label?: string;
  unit?: string;
  description?: string;
}

export interface PortSpec {
  type: string;
  multi?: boolean;
  optional?: boolean;
}

export type NodeInputs = Record<string, PortSpec>;
export type NodeOutputs = Record<string, PortSpec>;
