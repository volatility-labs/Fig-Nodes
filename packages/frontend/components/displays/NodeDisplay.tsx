// components/displays/NodeDisplay.tsx
// Routes display rendering to the appropriate component based on type

import { OutputDisplayType, type OutputDisplayOptions } from '@sosa/core';
import { ChartDisplay } from './ChartDisplay';
import { ImageDisplay } from './ImageDisplay';
import { TextDisplay } from './TextDisplay';
import { NoteDisplay } from './NoteDisplay';

interface NodeDisplayProps {
  type: OutputDisplayType;
  value: Record<string, unknown>;
  options?: OutputDisplayOptions;
}

export function NodeDisplay({ type, value, options }: NodeDisplayProps) {
  switch (type) {
    case OutputDisplayType.CHART_PREVIEW:
      return <ChartDisplay value={value} options={options} />;

    case OutputDisplayType.IMAGE_GALLERY:
    case OutputDisplayType.IMAGE_VIEWER:
      return <ImageDisplay value={value} options={options} />;

    case OutputDisplayType.TEXT_DISPLAY:
    case OutputDisplayType.TEXT_DISPLAY_DOM:
      return <TextDisplay value={value} options={options} />;

    case OutputDisplayType.NOTE_DISPLAY:
      return <NoteDisplay value={value} options={options} />;

    case OutputDisplayType.NONE:
      return null;

    default:
      // Fallback: render as JSON
      return (
        <pre className="fig-display-fallback">
          {JSON.stringify(value, null, 2)}
        </pre>
      );
  }
}
