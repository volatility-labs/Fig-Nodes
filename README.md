# Fig Nodes

Inspired by ComfyUI for AI and litegraph, Fig Nodes makes it easy to build professional grade trading bots with node based UI.

1. Intuitive plug and play UI to build asset universe scanning, trading, visualization, position management, and data services logic. 
2. Modular node design allowing any developer to build new nodes with custom logic with plug and play architecture. 
3. Lightweight design.

Created by Volatility Labs Inc. 

## Extending Error Handling

To customize the error display popup, import `showError` from `ui/static/utils/uiUtils.ts` and reassign it to your custom function.

For example, in a script:

```typescript
import { showError } from './utils/uiUtils';

showError = (message: string) => {
    // Your custom error handling logic here
    console.error(message);
    alert(`Custom Error: ${message}`);
};
```

This allows overriding the default popup with custom UI or behavior while keeping the system lightweight. 

# Testing

To run the unit tests:

poetry run python -m pytest tests/unit/ 