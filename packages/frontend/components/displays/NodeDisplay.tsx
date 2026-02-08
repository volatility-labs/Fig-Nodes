// components/displays/NodeDisplay.tsx
// Routes display rendering to the appropriate component based on type

import type { OutputDisplayType, OutputDisplayOptions } from '@sosa/core';
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
    case 'chart-preview':
      return <ChartDisplay value={value} options={options} />;

    case 'image-gallery':
    case 'image-viewer':
      return <ImageDisplay value={value} options={options} />;

    case 'text-display':
    case 'text-display-dom':
      return <TextDisplay value={value} options={options} />;

    case 'note-display':
      return <NoteDisplay value={value} options={options} />;

    case 'none':
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
