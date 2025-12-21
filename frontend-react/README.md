# Fig Nodes - React Wrapper

This directory contains the **React wrapper** for Fig Nodes. It wraps your existing Litegraph canvas implementation with modern React UI chrome (sidebars, navigation, modals, etc.).

## 🎯 Architecture

```
┌─────────────────────────────────────────┐
│  React Shell (This Directory)          │
│  - Top Navigation                       │
│  - Sidebar (Node Palette)              │
│  - Properties Panel                     │
│                                         │
│    ┌──────────────────────────────┐    │
│    │  Litegraph Canvas            │    │
│    │  (../frontend - Unchanged)   │    │
│    │                              │    │
│    └──────────────────────────────┘    │
└─────────────────────────────────────────┘
```

**Key Principle:** Your existing Litegraph canvas (`../frontend`) is **not modified**. The React wrapper just provides UI chrome around it.

---

## 🚀 Getting Started

### Prerequisites

- Node.js 20+ and yarn installed
- Your existing Fig Nodes backend running (`uv run python main.py --dev`)

### Installation

```bash
cd frontend-react
yarn install
```

### Development

```bash
# Start React dev server (port 5174)
yarn dev
```

The React wrapper will run on `http://localhost:5174` and proxy API calls to your FastAPI backend on port 8000.

**Note:** Your existing frontend (`../frontend`) runs on port 5173. The React wrapper uses 5174 to avoid conflicts during development.

---

## 📁 Project Structure

```
frontend-react/
├── src/
│   ├── App.tsx                    # Main app component
│   ├── App.css                    # App layout styles
│   ├── main.tsx                   # Entry point
│   ├── index.css                  # Global styles
│   │
│   ├── components/
│   │   ├── LitegraphEditor.tsx   # Wrapper that mounts your canvas
│   │   ├── LitegraphEditor.css
│   │   ├── TopNav.tsx            # Top navigation bar
│   │   ├── TopNav.css
│   │   ├── Sidebar.tsx           # Left sidebar (nodes, assets)
│   │   ├── Sidebar.css
│   │   ├── PropertiesPanel.tsx   # Right properties panel
│   │   └── PropertiesPanel.css
│   │
│   ├── hooks/                     # Custom React hooks (coming soon)
│   ├── services/                  # API clients, etc. (coming soon)
│   └── stores/                    # State management (coming soon)
│
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md (this file)
```

---

## 🔌 How It Works

### 1. LitegraphEditor Component

The `LitegraphEditor` component is the bridge between React and your existing Litegraph canvas:

```tsx
// components/LitegraphEditor.tsx
import { EditorInitializer } from '@legacy/services/EditorInitializer';

export function LitegraphEditor({ onEditorReady }) {
  useEffect(() => {
    const initializer = new EditorInitializer();
    initializer.createEditor(containerRef.current).then(editor => {
      onEditorReady(editor);
    });
  }, []);
  
  return <div ref={containerRef}>
    {/* Your existing canvas structure */}
  </div>;
}
```

**This component does NOT modify your Litegraph code.** It just:
1. Imports your existing `EditorInitializer`
2. Mounts it in a React component
3. Passes the editor instance back to React via callback

### 2. Path Aliases

The `tsconfig.json` and `vite.config.ts` are configured with path aliases:

- `@legacy/*` → Points to `../frontend` (your existing Litegraph code)
- `@components/*` → Points to `src/components`
- `@hooks/*` → Points to `src/hooks`
- etc.

This lets you import from both the legacy frontend and the new React code:

```tsx
import { EditorInitializer } from '@legacy/services/EditorInitializer';
import { Sidebar } from '@components/Sidebar';
```

### 3. Communication Between Layers

**React → Litegraph** (Commands):
```tsx
function Sidebar({ editor }) {
  const addNode = (nodeType: string) => {
    // Call into your existing Litegraph API
    const node = LiteGraph.createNode(nodeType);
    editor.graph.add(node);
    editor.canvas.draw(true, true);
  };
}
```

**Litegraph → React** (Events):
```tsx
function App() {
  const [selectedNode, setSelectedNode] = useState(null);
  
  useEffect(() => {
    // Listen to Litegraph events
    if (editor?.canvas) {
      editor.canvas.onNodeSelected = (node) => {
        setSelectedNode(node);
      };
    }
  }, [editor]);
}
```

---

## 🎨 Styling

The wrapper uses the same **Bloomberg Terminal theme** as your existing Litegraph frontend:

```css
:root {
  --theme-bg: #0d1117;
  --theme-text: #adbac7;
  --theme-accent: #539bf5;
  /* ... etc */
}
```

All React components use these CSS variables, so the styling is consistent with your existing canvas.

---

## 📦 Dependencies

### Core
- **React 18** - UI framework
- **React DOM** - DOM rendering
- **TypeScript** - Type safety
- **Vite** - Build tool (fast HMR)

### State Management & Data Fetching
- **@tanstack/react-query** - Server state management (for cloud API calls)
- **zustand** - Client state management (lightweight alternative to Redux)

### Coming Soon (Not Installed Yet)
- `@auth0/auth0-react` - Authentication
- `react-router-dom` - Routing (for multi-page app)
- UI component library (Shadcn, Radix, or similar)

---

## 🚧 Current Status

### ✅ What Works Now
- React wrapper renders around Litegraph canvas
- Top navigation bar
- Left sidebar (placeholder UI)
- Right properties panel (placeholder UI)
- Canvas mounts and initializes your existing Litegraph editor
- File operations (New, Load, Save, Execute) still work

### 🔨 What's Next (To Do)
1. **Connect Sidebar to Node Palette**
   - Fetch node types from backend
   - Implement "add node" functionality
   - Replace Tab-based palette with React sidebar

2. **Properties Panel**
   - Listen to node selection events
   - Display selected node properties
   - Enable editing properties from React UI

3. **Authentication**
   - Add Auth0 integration
   - Login/signup UI
   - Protect routes

4. **Cloud Features**
   - Graph browser modal
   - Workspace selector
   - Save/load from cloud
   - Version history

5. **Advanced Features**
   - Settings modal
   - User profile dropdown
   - Help/docs sidebar
   - Keyboard shortcuts panel

---

## 🔧 Development Tips

### Hot Module Replacement (HMR)

React components hot reload instantly. If you edit:
- `src/components/Sidebar.tsx` → Sidebar updates without page reload
- `src/App.css` → Styles update without page reload

Your Litegraph canvas doesn't hot reload (it's not set up for it), but that's okay - you rarely need to edit it.

### Debugging

**React DevTools:**
- Install React DevTools browser extension
- Inspect component state, props, etc.

**Litegraph DevTools:**
- Your existing performance profiler still works
- Access via: `window.performanceProfiler.getStats()`

### TypeScript

The project is fully typed. If you get type errors:
- Check `tsconfig.json` paths
- Make sure you're importing from correct aliases
- Add type declarations in `src/types/` if needed

---

## 📖 Examples

### Example 1: Add a New React Component

```tsx
// src/components/GraphBrowser.tsx
export function GraphBrowser({ onClose, onSelectGraph }) {
  const { data: graphs } = useQuery({
    queryKey: ['graphs'],
    queryFn: () => fetch('/api/v1/graphs').then(r => r.json())
  });
  
  return (
    <div className="modal">
      <h2>Your Graphs</h2>
      {graphs?.map(g => (
        <div key={g.id} onClick={() => onSelectGraph(g.id)}>
          {g.name}
        </div>
      ))}
    </div>
  );
}
```

### Example 2: Call Litegraph API from React

```tsx
// src/components/Sidebar.tsx
const addPolygonNode = () => {
  if (!editor) return;
  
  // Use your existing Litegraph API
  const { LiteGraph } = await import('@fig-node/litegraph');
  const node = LiteGraph.createNode('PolygonStockUniverse');
  
  // Place in center of viewport
  const canvas = editor.canvas;
  const rect = canvas.canvas.getBoundingClientRect();
  node.pos = [rect.width / 2, rect.height / 2];
  
  editor.graph.add(node);
  editor.canvas.draw(true, true);
};
```

### Example 3: Listen to Litegraph Events

```tsx
// src/App.tsx
useEffect(() => {
  if (!editor) return;
  
  // Listen to graph changes
  const originalAdd = editor.graph.add.bind(editor.graph);
  editor.graph.add = (node) => {
    originalAdd(node);
    console.log('Node added:', node);
    // Update React state here if needed
  };
}, [editor]);
```

---

## 🚀 Deployment

### Development
```bash
yarn dev
```
Runs React on port 5174, proxies to backend on port 8000.

### Production Build
```bash
yarn build
```
Builds optimized bundle to `dist/`. You can serve this with your FastAPI backend (similar to how you serve the current frontend).

### Integration with Existing Build
Eventually, you'll want to:
1. Build React wrapper: `cd frontend-react && yarn build`
2. Copy `dist/` to FastAPI static folder
3. Serve from FastAPI like you do now

---

## 🤔 Questions?

### Why not just rebuild everything in React?
- Your Litegraph canvas works perfectly and is highly optimized
- Rebuilding would take 6-12 months with high risk
- This wrapper approach takes 7-10 weeks with low risk

### Can I still use the old frontend during development?
- Yes! The old frontend runs on port 5173
- The React wrapper runs on port 5174
- They can run simultaneously

### Will this work with my existing Python backend?
- Yes! The React wrapper proxies all API calls to port 8000
- Your backend doesn't need any changes
- WebSocket support works the same

### What about the node palette? Will I lose Tab-based node adding?
- No! Your existing palette still works
- The React sidebar is an enhancement, not a replacement (for now)
- You can gradually migrate features from Tab palette to React sidebar

---

## 📚 Next Steps

1. **Run the React wrapper:**
   ```bash
   cd frontend-react
   yarn install
   yarn dev
   ```

2. **Try adding functionality:**
   - Edit `src/components/Sidebar.tsx` to fetch real node types
   - Implement node adding from sidebar
   - Connect properties panel to selected nodes

3. **Add cloud features:**
   - Install Auth0: `yarn add @auth0/auth0-react`
   - Create graph browser modal
   - Implement save/load from cloud

4. **Deploy:**
   - Build production bundle
   - Integrate with FastAPI
   - Deploy to cloud

---

**Remember:** This wrapper doesn't replace your Litegraph canvas - it enhances it with modern React UI. Your existing code continues to work unchanged.

Happy coding! 🚀

