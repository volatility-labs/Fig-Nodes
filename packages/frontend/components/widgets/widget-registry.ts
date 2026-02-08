// widget-registry.ts
// Central registry for widget renderers — replaces the switch/case in BodyWidget

import type React from 'react';
import type { DataSource } from '@fig-node/core';

export interface WidgetProps {
  widget: {
    type: string;
    id: string;
    label?: string;
    bind?: string;
    options?: Record<string, unknown>;
    dataSource?: DataSource;
  };
  value: unknown;
  onChange: (value: unknown) => void;
}

export type WidgetRenderer = React.FC<WidgetProps>;

const registry = new Map<string, WidgetRenderer>();

export function registerWidget(type: string, renderer: WidgetRenderer): void {
  registry.set(type, renderer);
}

export function getWidget(type: string): WidgetRenderer | undefined {
  return registry.get(type);
}
