Rete.js Render utils
====
[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://stand-with-ukraine.pp.ua)
[![Discord](https://img.shields.io/discord/1081223198055604244?color=%237289da&label=Discord)](https://discord.gg/cxSFkPZdsV)

**Rete.js utils**

## Key features

- **Basic connection paths**: provides the classic and loop SVG paths
- **Sockets position**: enables the calculation of socket positions
  - **DOM-based**: calculates the position of sockets using `offsetTop`/`offsetLeft`

## Getting Started

Before using this package, make sure to install it as a **peer** and **dev** dependency into your the render plugin.

This package exposes `getDOMSocketPosition`, which is a `SocketPositionWatcher` type and used by default in render plugins.

```ts
import { getDOMSocketPosition } from 'rete-render-utils';

const socketsPositionWatcher = getDOMSocketPosition<Schemes, AreaExtra>(area)

socketPositionWatcher.attach(area)

const unwatch = positionWatcher.listen(nodeId, portSide, portKey, (position) => {
  /// called when the socket position changes
})
```

The render plugins also use its default implementations for rendering connection paths using `classicConnectionPath` and `loopConnectionPath`.

```ts
import { classicConnectionPath } from 'rete-render-utils';

const curvature = 0.3
const points = [sourcePoint, targetPoint] // should contain two points
const svgPath = classicConnectionPath(points, curvature)
```

## Contribution

Please refer to the [Contribution](https://retejs.org/docs/contribution) guide

## License

[MIT](https://github.com/retejs/render-utils-plugin/blob/main/LICENSE)
