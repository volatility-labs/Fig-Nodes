# Fig Nodes (Beta)

Node-based workflow tool for traders to build and execute agentic graph pipelines — scan markets, research ideas, integrate LLMs for filtering and reasoning, and more.

## Architecture

Fig Nodes is a TypeScript monorepo (Yarn workspaces) with four packages:

```
fig-node/
├── packages/
│   ├── core/          # Framework-agnostic graph execution engine
│   ├── server/        # Fastify HTTP + WebSocket server
│   ├── frontend/      # Vite-based graph editor UI
│   └── litegraph/     # Maintained fork of litegraph.js
├── nodes/             # Built-in node implementations
│   ├── io/            # Input/output (text input, logging, Discord, X/Twitter)
│   ├── llm/           # LLM chat, vision, message building, tool use
│   └── market/        # Market data, technical filters, indicators, charting
├── custom_nodes/      # Drop-in directory for user-defined nodes
└── .env.example       # Environment variable template
```

**Core** (`@fig-node/core`) — the graph execution engine. Computes a topological sort of the node graph, executes nodes in parallel within each dependency level, and supports cancellation via AbortController. Exports the `GraphExecutor`, node registry, `Base` node class, and shared types (`SerialisableGraph`, `ExecutionResults`, `ProgressEvent`). Has no server or frontend dependencies.

**Server** (`@fig-node/server`) — a Fastify server that imports Core to execute graphs. Exposes a REST API (`GET /api/v1/nodes` for node metadata) and a WebSocket endpoint (`/execute`) for real-time graph execution with progress streaming. Jobs run through a FIFO execution queue (one at a time), with IO-category nodes streaming results immediately.

**Frontend** (`@fig-node/frontend`) — a Vite app that provides a canvas-based graph editor using the litegraph fork. Fetches node metadata from the server at startup and dynamically registers nodes. Connects to the server over WebSocket for execution. The frontend is a generic renderer — node UI is entirely driven by backend-defined metadata (`paramsMeta`, `uiConfig`).

**Litegraph** (`@fig-node/litegraph`) — a maintained fork of [litegraph.js](https://github.com/Comfy-Org/litegraph.js) providing the `LGraph`, `LGraphCanvas`, and `LGraphNode` classes for the graph editor.

The server and frontend run as **separate processes**. In development, the Vite dev server proxies `/api/*` and `/execute` (including WebSocket upgrades) to the Fastify server.

## Requirements

- Node.js >= 20.0.0
- Yarn 1.22.22

## Installation

```bash
git clone https://github.com/volatility-labs/Fig-Nodes.git
cd Fig-Nodes
yarn install
```

`yarn install` automatically builds the litegraph and core packages via the `postinstall` script.

## Environment Variables

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Used By |
|---|---|
| `POLYGON_API_KEY` | Market data nodes (Polygon universe, custom bars, ORB filter, industry filter) |
| `TAVILY_API_KEY` | Web search tool node |
| `OPENROUTER_API_KEY` | LLM chat and vision nodes (set in the frontend API key manager) |

## Development

Start all four packages concurrently:

```bash
yarn dev
```

This runs:

| Package | Command | Port |
|---|---|---|
| litegraph | `vite` (watch mode) | — |
| core | `tsc --watch` | — |
| server | `tsx watch` | 8000 |
| frontend | `vite dev` | 5173 |

Open `http://localhost:5173` in your browser. The default graph should load — press **Execute** at the bottom right of the canvas.

## Production Build

```bash
yarn build
```

Builds in order: litegraph → core → nodes → server.

## Custom Nodes

Create a `.ts` file in the `custom_nodes/` directory. Extend the `Base` class from `@fig-node/core`:

```typescript
import { Base, NodeCategory } from '@fig-node/core';

export class MyCustomNode extends Base {
  static inputs = { text: 'string' };
  static outputs = { result: 'string' };
  static CATEGORY = NodeCategory.IO;

  protected async executeImpl(inputs: Record<string, unknown>) {
    return { result: `Processed: ${inputs.text}` };
  }
}
```

Nodes are auto-discovered at server startup — no registration needed.

## Built-in Nodes

**IO** — TextInput, AssetSymbolInput, Logging, SaveOutput, SystemPromptLoader, Note, DiscordOutput, XcomUsersFeed

**LLM** — OpenRouterChat, OpenRouterVisionChat, LLMMessagesBuilder, TextToLLMMessage, ToolsBuilder (with web search and tool registry services)

**Market** — Polygon stock/crypto universe, custom bars, batch custom bars, 15 technical filters (ADX, ATR, RSI, EMA range, SMA crossover, VBP levels, etc.), indicators (ATR, ATRX, ORB), charting (OHLCV chart, Hurst plot, image display), and utility nodes (extract symbols, price data fetching)

## Scripts

| Command | Description |
|---|---|
| `yarn dev` | Start all packages in development mode |
| `yarn build` | Production build (litegraph → core → nodes → server) |
| `yarn build:nodes` | Build only the nodes directory |
| `yarn test` | Run tests across all workspaces |
| `yarn lint` | Lint all workspaces |
| `yarn typecheck` | Type-check all workspaces |

## License

Fig Nodes is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
