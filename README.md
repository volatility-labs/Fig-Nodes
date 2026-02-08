# Sosa

Node-based workflow tool for building and executing agentic graph pipelines — scan markets, research ideas, integrate LLMs for filtering and reasoning, and more.

## Architecture

Sosa is a TypeScript monorepo (Yarn workspaces) with three packages:

```
sosa/
├── packages/
│   ├── core/          # Framework-agnostic graph execution engine
│   ├── server/        # Fastify HTTP + WebSocket server
│   └── frontend/      # Rete.js v2-based graph editor UI
├── nodes/             # Built-in node implementations
│   ├── io/            # Input/output (text input, logging, Discord, X/Twitter)
│   ├── llm/           # LLM chat, vision, message building, tool use
│   └── market/        # Market data, technical filters, indicators, charting
├── custom_nodes/      # Drop-in directory for user-defined nodes
└── .env.example       # Environment variable template
```

**Core** (`@sosa/core`) — Graph execution engine. Topological sort, parallel execution within dependency levels, cancellation via AbortController. Exports `GraphExecutor`, node registry, `Node` base class, and shared types.

**Server** (`@sosa/server`) — Fastify server with REST API (`GET /api/v1/nodes`) and WebSocket endpoint (`/execute`) for real-time execution with progress streaming. FIFO execution queue with IO nodes streaming results immediately.

**Frontend** (`@sosa/frontend`) — Vite + React app with a Rete.js v2 graph editor. Node UI is entirely driven by backend-defined metadata (`paramsMeta`, `uiConfig`).

The server and frontend run as separate processes. In dev, Vite proxies `/api/*` and `/execute` to the Fastify server.

## Getting Started

### Requirements

- Node.js >= 20.0.0
- Yarn 1.22.22

### Install

```bash
git clone <repo-url>
cd sosa
yarn install
```

### Environment Variables

```bash
cp .env.example .env
```

| Variable | Used By |
|---|---|
| `POLYGON_API_KEY` | Market data nodes |
| `TAVILY_API_KEY` | Web search tool node |
| `OPENROUTER_API_KEY` | LLM chat and vision nodes |

### Development

```bash
yarn dev
```

| Package | Command | Port |
|---|---|---|
| core | `tsc --watch` | — |
| server | `tsx watch` | 8000 |
| frontend | `vite dev` | 5173 |

Open `http://localhost:5173` and press **Execute**.

### Production Build

```bash
yarn build
```

## Custom Nodes

Create a `.ts` file in `custom_nodes/`. Extend the `Node` class from `@sosa/core`:

```typescript
import { Node, NodeCategory } from '@sosa/core';

export class MyCustomNode extends Node {
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

**LLM** — OpenRouterChat, OpenRouterVisionChat, LLMMessagesBuilder, TextToLLMMessage, ToolsBuilder

**Market** — Polygon stock/crypto universe, custom bars, batch custom bars, 15 technical filters (ADX, ATR, RSI, EMA range, SMA crossover, VBP levels, etc.), indicators (ATR, ATRX, ORB), charting (OHLCV chart, Hurst plot, image display), and utility nodes (extract symbols, price data fetching)

## Scripts

| Command | Description |
|---|---|
| `yarn dev` | Start all packages in dev mode |
| `yarn build` | Production build (core → nodes → server) |
| `yarn build:nodes` | Build only the nodes directory |
| `yarn test` | Run tests across all workspaces |
| `yarn lint` | Lint all workspaces |
| `yarn typecheck` | Type-check all workspaces |

## License

Sosa is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
