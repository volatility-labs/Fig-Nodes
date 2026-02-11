// widget-registry.ts
// Static widget renderer map keyed by BodyWidgetType

import type React from 'react';
import { BodyWidgetType, type BodyWidget } from '@sosa/core';

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
  [BodyWidgetType.TEXT]: TextWidget as WidgetRenderer,
  [BodyWidgetType.TEXTAREA]: TextareaWidget as WidgetRenderer,
  [BodyWidgetType.CODE]: TextareaWidget as WidgetRenderer,
  [BodyWidgetType.JSON]: TextareaWidget as WidgetRenderer,
  [BodyWidgetType.NUMBER]: NumberWidget as WidgetRenderer,
  [BodyWidgetType.INTEGER]: NumberWidget as WidgetRenderer,
  [BodyWidgetType.INT]: NumberWidget as WidgetRenderer,
  [BodyWidgetType.FLOAT]: NumberWidget as WidgetRenderer,
  [BodyWidgetType.COMBO]: ComboWidget as WidgetRenderer,
  [BodyWidgetType.BOOLEAN]: BooleanWidget as WidgetRenderer,
  [BodyWidgetType.PROGRESS]: ProgressWidget as WidgetRenderer,
  [BodyWidgetType.STATUS]: StatusWidget as WidgetRenderer,
};

/** Look up a widget renderer by type. */
export function getWidget(type: string): WidgetRenderer | undefined {
  return WIDGETS[type as BodyWidgetType];
}
