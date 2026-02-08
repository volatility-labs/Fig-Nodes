## Overview

This directory contains the frontend code for Fig Nodes — a Vite + React application that provides a visual graph editor built on [Rete.js v2](https://retejs.org/).

## Architecture

- **Rete Editor** (`components/editor/`) — the graph editor is the single source of truth for graph structure at runtime. The `ReteAdapter` manages node/edge CRUD and serializes the graph on demand for execution or saving.
- **Stores** (`stores/graphStore.ts`) — Zustand store for execution-related reactive state (node status, progress, notifications). Graph structure itself lives in Rete, not the store.
- **Services** (`services/`) — WebSocket client for execution, file manager for save/load, execution status tracking.
- **Displays** (`components/displays/`) — pluggable display components rendered inside nodes based on execution output type (text, images, charts, notes).

## Node UI

Node appearance and widgets are entirely driven by backend-defined metadata (`paramsMeta`, `uiConfig`). The frontend dynamically creates editor nodes with typed sockets based on the metadata fetched from `GET /api/v1/nodes` at startup. No per-node UI code is needed in the frontend.
