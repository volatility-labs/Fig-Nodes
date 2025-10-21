# UI/Static Frontend

## Overview
This directory contains the TypeScript frontend for the node-based editor, built with LiteGraph and Vite.

## Structure
- `app.ts`: Main entry point.
- `components/`: Reusable UI components (e.g., NodeList.ts).
- `nodes/`: Custom node UI classes (extend BaseCustomNode.ts).
- `utils/`: Helper functions (e.g., websocket.ts).
- `tests/`: Vitest tests.
- `types.ts`: Type handling.
- `style.css`: Styles.
- `index.html`: HTML template.

## Development
- Install: `yarn install`
- Run: `yarn dev`
- Build: `yarn build`
- Test: `yarn test`
- Lint: `yarn lint`
- Format: `yarn format`

## Adding a New Node UI
1. Create `nodes/MyNodeUI.ts` extending BaseCustomNode.ts.
2. In backend (ui/server.py), set "uiModule": "MyNodeUI" for the node.
3. Add tests in tests/.
