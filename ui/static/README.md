# UI/Static Frontend

## Overview
This directory contains the TypeScript frontend for the node-based editor, built with LiteGraph and Vite.

## Structure
- `app.ts`: Main entry point.
- `components/`: Reusable UI components (e.g., NodeList.ts).
- `nodes/`: Custom node UI classes (extend BaseCustomNode.ts).
- `services/`: Core services (APIKeyManager, FileManager, etc.).
- `tests/`: Vitest tests.
- `types.ts`: Type handling.
- `resultTypes.ts`: Execution result type definitions.
- `websocketType.ts`: WebSocket message type definitions.
- `websocket.ts`: WebSocket communication handler.
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
1. Create `nodes/{category}/{BackendClassName}NodeUI.ts` extending BaseCustomNode.ts.
   - Example: For backend class `MyNode`, create `nodes/io/MyNodeNodeUI.ts`
   - The UI class must be named `{BackendClassName}NodeUI`
2. The UI module will be automatically discovered based on the naming convention.
3. Add tests in tests/.
