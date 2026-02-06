// components/displays/ImageDisplay.tsx
// Renders image gallery or single image viewer

// ImageDisplay component
import type { OutputDisplayOptions } from '@fig-node/core';

interface ImageDisplayProps {
  value: Record<string, unknown>;
  options?: OutputDisplayOptions;
}

export function ImageDisplay({ value, options }: ImageDisplayProps) {
  // Support both single image and gallery
  const images: string[] = [];

  if (typeof value.image === 'string') {
    images.push(value.image);
  } else if (Array.isArray(value.images)) {
    images.push(...(value.images as string[]));
  } else if (typeof value.url === 'string') {
    images.push(value.url);
  }

  if (images.length === 0) {
    return <div className="fig-display-empty">{options?.emptyText ?? 'No images'}</div>;
  }

  return (
    <div className="fig-display-images nodrag nowheel">
      {images.map((src, i) => (
        <img
          key={i}
          src={src}
          alt={`Output ${i + 1}`}
          className="fig-display-image"
          style={{
            maxWidth: '100%',
            objectFit: options?.preserveAspectRatio !== false ? 'contain' : 'fill',
          }}
        />
      ))}
    </div>
  );
}
