// components/displays/NoteDisplay.tsx
// Renders a note/sticky display in a node

import type { OutputDisplayOptions } from '@fig-node/core';

interface NoteDisplayProps {
  value: Record<string, unknown>;
  options?: OutputDisplayOptions;
}

export function NoteDisplay({ value, options }: NoteDisplayProps) {
  const text = typeof value.text === 'string'
    ? value.text
    : typeof value.note === 'string'
      ? value.note
      : JSON.stringify(value, null, 2);

  return (
    <div
      className="fig-display-note nodrag nowheel"
      style={{
        backgroundColor: options?.uniformColor ?? '#3a3a20',
      }}
    >
      <pre className="fig-display-note-content">{text}</pre>
    </div>
  );
}
