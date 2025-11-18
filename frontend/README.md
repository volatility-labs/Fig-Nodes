## Overview
This directory contains the frontend code for Fig node. 

## Adding a New Node UI
1. Create `nodes/{category}/{BackendClassName}NodeUI.ts` extending BaseCustomNode.ts.
   - Example: For backend class `MyNode`, create `nodes/io/MyNodeNodeUI.ts`
   - The UI class must be named `{BackendClassName}NodeUI`
2. The UI module will be automatically discovered based on the naming convention.
