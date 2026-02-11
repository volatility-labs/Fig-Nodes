// widget-registry.ts
// Static widget renderer map keyed by BodyWidgetType

import type React from 'react';
import type { BodyWidget, BodyWidgetType } from '@sosa/core';

import TextWidget from './TextWidget';
import TextareaWidget from './TextareaWidget';
import NumberWidget from './NumberWidget';
import ComboWidget from './ComboWidget';
import BooleanWidget from './BooleanWidget';
import ProgressWidget from './ProgressWidget';
import StatusWidget from './StatusWidget';

// ============ Types ============

export interface WidgetProps<TWidget extends BodyWidget = BodyWidget> {
  widget: TWidget;
  value: unknown;
  onChange: (value: unknown) => void;
}

export type WidgetRenderer<TWidget extends BodyWidget = BodyWidget> = React.FC<WidgetProps<TWidget>>;

// ============ Static Registry ============

/** All widget renderers, keyed by BodyWidgetType. */
export const WIDGETS: Partial<Record<BodyWidgetType, WidgetRenderer>> = {
  text: TextWidget as WidgetRenderer,
  textarea: TextareaWidget as WidgetRenderer,
  code: TextareaWidget as WidgetRenderer,
  json: TextareaWidget as WidgetRenderer,
  number: NumberWidget as WidgetRenderer,
  integer: NumberWidget as WidgetRenderer,
  int: NumberWidget as WidgetRenderer,
  float: NumberWidget as WidgetRenderer,
  combo: ComboWidget as WidgetRenderer,
  boolean: BooleanWidget as WidgetRenderer,
  progress: ProgressWidget as WidgetRenderer,
  status: StatusWidget as WidgetRenderer,
};

/** Look up a widget renderer by type. */
export function getWidget(type: string): WidgetRenderer | undefined {
  return WIDGETS[type as BodyWidgetType];
}
