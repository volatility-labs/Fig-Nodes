// components/widgets/BodyWidget.tsx
// Thin dispatcher: looks up widget type in registry → delegates rendering

import { memo } from 'react';
import { BodyWidgetType } from '@sosa/core';
import { getWidget, type WidgetProps } from './widget-registry';

// Re-export WidgetProps so existing consumers don't break
export type { WidgetProps };
export type BodyWidgetProps = WidgetProps;

export const BodyWidget = memo(function BodyWidget(props: WidgetProps) {
  const Renderer = getWidget(props.widget.type);
  if (!Renderer) {
    console.warn(`Unknown widget type: "${props.widget.type}", falling back to text`);
    const FallbackRenderer = getWidget(BodyWidgetType.TEXT)!;
    return <FallbackRenderer {...props} />;
  }
  return <Renderer {...props} />;
});
