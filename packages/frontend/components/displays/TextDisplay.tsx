// components/displays/TextDisplay.tsx
// Renders text/DOM output in a node display area

import { useMemo } from 'react';
import type { OutputDisplayOptions } from '@sosa/core';

interface TextDisplayProps {
  value: Record<string, unknown>;
  options?: OutputDisplayOptions;
}

export function TextDisplay({ value, options }: TextDisplayProps) {
  const text = useMemo(() => {
    // Extract text from various result shapes
    if (typeof value.text === 'string') return value.text;
    if (typeof value.output === 'string') return value.output;
    if (typeof value.result === 'string') return value.result;
    if (typeof value.log === 'string') return value.log;
    // Fallback: stringify the entire value
    return JSON.stringify(value, null, 2);
  }, [value]);

  return (
    <div
      className={`fig-display-text nodrag nowheel ${options?.scrollable ? 'scrollable' : ''}`}
    >
      <pre className="fig-display-text-content">{text}</pre>
      {options?.copyButton && (
        <button
          className="fig-display-copy-btn"
          onClick={() => navigator.clipboard.writeText(text)}
          title="Copy to clipboard"
        >
          📋
        </button>
      )}
    </div>
  );
}
