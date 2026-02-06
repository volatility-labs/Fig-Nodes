// app.ts — Entry point for the fig-node graph editor
// Mounts the React Flow editor and initializes services

import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './components/App';

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('root');
  if (!container) {
    console.error('Root container not found');
    return;
  }

  const root = createRoot(container);
  root.render(React.createElement(App));
});
