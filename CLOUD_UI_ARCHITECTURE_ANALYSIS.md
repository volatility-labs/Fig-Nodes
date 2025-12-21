# Fig Nodes Cloud UI Architecture Analysis

**Date:** December 16, 2025  
**Purpose:** Evaluate technology options for Fig Nodes cloud version  
**Options Considered:** React, PixiJS, Enhanced Litegraph

---

## Executive Summary

**Recommendation: Keep and enhance your forked Litegraph implementation** rather than migrating to React or PixiJS. Your current architecture is production-ready, performant, and would require significant rewrite effort to match with React or PixiJS.

**Key Reasons:**
- ✅ You've already invested heavily in a solid, performant fork of Litegraph
- ✅ Your TypeScript/Vite architecture is modern and maintainable
- ✅ Cloud deployment is straightforward with your existing FastAPI + built frontend
- ✅ Migration to React/PixiJS would take 3-6+ months with high risk
- ✅ Litegraph is purpose-built for node-based workflows; React/PixiJS are not

---

## Current Architecture Analysis

### What You Have Built

Your codebase represents a **sophisticated, production-ready node graph editor** with:

#### 1. **Forked & Enhanced Litegraph (`@fig-node/litegraph`)**
- **Location:** `frontend/fignode-litegraph.js/`
- **91 TypeScript source files** with full type safety
- **Custom modifications:**
  - UUID-based node/link system
  - Enhanced serialization (subgraphs, reroutes, floating links)
  - Custom event system (`CustomEventTarget`)
  - Advanced layout algorithms (auto-align, bounds fitting)
  - Performance profiling infrastructure
  - Extensible rendering pipeline

#### 2. **Modern TypeScript Frontend**
- **Vite** build system (fast HMR, optimized production builds)
- **Service-based architecture:**
  - `ServiceRegistry` for dependency injection
  - `ThemeManager` with Bloomberg Terminal theme
  - `TypeColorRegistry` for consistent type visualization
  - `PerformanceProfiler` for optimization
  - `FileManager` with autosave
  - `APIKeyManager` for external services
- **55+ custom nodes** across market, LLM, I/O, and utility categories
- **Modular node system:**
  - `BaseCustomNode` with composition pattern
  - `NodeWidgetManager`, `NodeRenderer`, `NodeInteractions`
  - Type-safe input/output system
  - Progress tracking and error handling

#### 3. **Runtime Optimizations**
- **Custom wheel event patching** for Mac trackpad support
- **Conditional background rendering** (30-50% fewer draw calls when zoomed out)
- **Native `clearRect` optimization**
- **Watch mode** for Litegraph during development
- **WebSocket streaming** for real-time execution updates

#### 4. **Python Backend Integration**
- **FastAPI** server with WebSocket support
- **Queue system** for graph execution
- **Session management**
- **Polygon, OpenRouter, Ollama integrations**
- **Indicator calculators** (23+ technical indicators)

#### 5. **Production Deployment Ready**
```bash
uv run python main.py --prod
```
- Builds frontend to `dist/`
- Serves static assets via FastAPI
- Single port deployment (backend proxies frontend)
- WebSocket support configured (5-minute timeouts for large transfers)

---

## Option 1: React (with React Flow or custom canvas)

### What React Would Give You

**Pros:**
- ✅ Rich ecosystem (React Query, Zustand, etc.)
- ✅ Component reusability
- ✅ Familiar to many developers
- ✅ Good for UI chrome (sidebars, modals, forms)

**Cons:**
- ❌ **React is NOT optimized for canvas-heavy node graphs**
- ❌ React Flow (best React node library) is:
  - Limited to 1000-2000 nodes before performance degrades
  - Your requirement: "10k+ nodes with rustworkx"
  - React Flow uses HTML divs (slow) or SVG (also slow at scale)
- ❌ **Custom canvas rendering in React:**
  - You'd essentially rebuild Litegraph from scratch
  - React reconciliation fights with imperative canvas APIs
  - Would take 6-12 months to match your current capabilities
- ❌ **Migration cost:**
  - Rewrite 91 Litegraph TypeScript files
  - Rewrite all 55+ custom nodes
  - Reimplement layout algorithms
  - Reimplement connection rendering
  - Rebuild undo/redo, copy/paste, serialization
  - High risk of bugs and regressions

### When React Makes Sense
- Simple node graphs (< 100 nodes)
- UI-heavy applications with occasional node graphs
- When you need server-side rendering (SSR)
- When React's component model is critical

### Your Use Case
- ❌ **Does NOT fit:** You need 10k+ node support
- ❌ **Does NOT fit:** Canvas-heavy, performance-critical rendering
- ✅ **Could work for:** Admin dashboards, user settings, marketing pages

---

## Option 2: PixiJS (WebGL rendering)

### What PixiJS Would Give You

**Pros:**
- ✅ Extremely fast WebGL rendering (GPU-accelerated)
- ✅ Can handle 10k+ objects smoothly
- ✅ Sprite-based rendering (good for repeated elements)
- ✅ Rich filters and effects
- ✅ Mobile-friendly (touch events)

**Cons:**
- ❌ **Not designed for node graphs** - you'd build everything from scratch:
  - Connection routing algorithms
  - Node layout algorithms
  - Input/output slot management
  - Text rendering (WebGL text is tricky)
  - UI widgets (inputs, dropdowns, sliders)
  - Context menus
  - Copy/paste, undo/redo
  - Serialization
- ❌ **"Too flashy" is a valid concern:**
  - PixiJS encourages particle effects, animations, filters
  - Professional financial tools should feel precise, not flashy
  - Your Bloomberg Terminal theme is perfect; PixiJS could undermine that
- ❌ **Integration complexity:**
  - Mixing HTML UI (forms, modals) with WebGL canvas is awkward
  - Accessibility is harder (screen readers, keyboard nav)
  - Debugging is harder (WebGL inspector needed)
- ❌ **Migration cost:**
  - 12-18 months to rebuild everything
  - Steeper learning curve than Canvas 2D
  - More points of failure (WebGL context loss, driver bugs)

### When PixiJS Makes Sense
- Games or highly animated interfaces
- Particle systems, visual effects
- Mobile games with thousands of sprites
- When you need WebGL shaders/filters

### Your Use Case
- ❌ **Does NOT fit:** Node graphs don't need WebGL (unless 50k+ nodes)
- ❌ **Does NOT fit:** Professional finance UX doesn't need flashy effects
- ✅ **Could work for:** If you hit performance limits with Canvas 2D (unlikely)

---

## Option 3: Enhance Your Litegraph Fork (RECOMMENDED)

### Why This Is The Right Choice

#### 1. **You're Already 80% There**
Your codebase is production-ready:
- ✅ Modern TypeScript with full type safety
- ✅ Vite build system (fast dev, optimized prod)
- ✅ Service-based architecture (maintainable, testable)
- ✅ 55+ nodes already implemented
- ✅ WebSocket streaming with progress bars
- ✅ Autosave, file management, themes
- ✅ Performance profiling built-in
- ✅ Mac trackpad support

#### 2. **Litegraph Is Purpose-Built For This**
- ✅ Designed for node graphs (not games, not forms)
- ✅ Canvas 2D is fast enough for 10k+ nodes with proper optimization
- ✅ You've already optimized it (conditional rendering, etc.)
- ✅ Rustworkx backend handles heavy computation; frontend just displays

#### 3. **Cloud Deployment Is Straightforward**
Your production mode already works:
```bash
# Build frontend
cd frontend && yarn build

# Serve from FastAPI
uv run python main.py --prod --host 0.0.0.0 --port 8000
```

**For cloud (paid users):**
- Deploy to AWS/GCP/Azure with Docker
- Add authentication (Auth0, Firebase, or custom JWT)
- Add user workspaces (PostgreSQL for user data)
- Add collaboration (sync graph state via WebSocket)
- Scale horizontally (graph execution in workers)

#### 4. **Low Risk, High Reward**
- ✅ Build on proven foundation
- ✅ Incremental improvements (not rewrite)
- ✅ Your team already understands the codebase
- ✅ No learning curve for new framework

### Recommended Enhancements for Cloud

#### Phase 1: Multi-User Foundation (1-2 months)
1. **Authentication & Authorization**
   - Integrate Auth0 or Firebase Authentication
   - JWT tokens for API/WebSocket auth
   - User roles (free, pro, enterprise)

2. **User Workspaces**
   - PostgreSQL for user data and graph storage
   - API endpoints: `GET/POST/DELETE /api/workspaces/:id/graphs`
   - Move from localStorage to cloud storage

3. **Cloud Infrastructure**
   - Docker container for FastAPI + built frontend
   - Deploy to AWS ECS, GCP Cloud Run, or Azure Container Apps
   - Redis for session management
   - S3/GCS/Azure Blob for graph storage

#### Phase 2: Collaboration Features (2-3 months)
4. **Real-Time Collaboration (optional)**
   - Operational Transformation or CRDT for graph merging
   - Show user cursors (like Figma)
   - Presence indicators ("Steve is editing node X")

5. **Version History**
   - Git-like commits for graphs
   - "Restore to version" functionality
   - Diff visualization

6. **Sharing & Permissions**
   - Share graphs with team members
   - Read-only vs edit permissions
   - Public graph gallery (optional)

#### Phase 3: Enterprise Features (3-4 months)
7. **Advanced Execution**
   - Queue system improvements (priority, cancellation)
   - Distributed execution (multiple workers)
   - Schedule graphs (cron jobs)
   - Webhook triggers

8. **Analytics & Monitoring**
   - Graph execution metrics
   - Performance dashboards
   - Error logging (Sentry)
   - Usage analytics

9. **API & Integrations**
   - REST API for graph execution
   - Webhook outputs
   - Zapier/Make.com integration
   - Export to Python/Node.js code

#### Phase 4: UI/UX Polish (ongoing)
10. **Enhanced Litegraph Features**
    - Mini-map (overview of large graphs)
    - Better search (fuzzy search nodes)
    - Node templates (save/load node configs)
    - Canvas comments/annotations
    - Improved mobile support (touch gestures)

11. **Professional UI Chrome**
    - React can be used HERE (sidebars, modals, settings)
    - Keep Litegraph canvas, wrap with React shell
    - Example: Figma uses canvas + React chrome

---

## Hybrid Approach: Litegraph Canvas + React Chrome

### Best of Both Worlds

If you want some React benefits without migration pain:

**Architecture:**
```
┌─────────────────────────────────────────┐
│  React Shell (Sidebar, Modals, Header)  │
│  ┌───────────────────────────────────┐  │
│  │                                   │  │
│  │   Litegraph Canvas (Full Screen)  │  │
│  │   (Your current implementation)   │  │
│  │                                   │  │
│  └───────────────────────────────────┘  │
│  React Footer (Status, Controls)        │
└─────────────────────────────────────────┘
```

**Benefits:**
- ✅ Keep your performant Litegraph canvas
- ✅ Use React for UI chrome (easier to build/maintain)
- ✅ Gradual migration (if desired)
- ✅ Access React ecosystem for non-canvas UI

**Implementation:**
1. Create React wrapper app
2. Mount Litegraph canvas in a React component
3. Use React for:
   - Node palette/search
   - Settings panels
   - User profile dropdown
   - Upgrade prompts
   - Help/docs sidebar
4. Keep Litegraph for:
   - Canvas rendering
   - Node graph logic
   - Execution flow

**Example Code:**
```tsx
// App.tsx
function App() {
  return (
    <div className="app">
      <Header />
      <div className="main">
        <Sidebar />
        <LitegraphCanvas />  {/* Your current canvas */}
      </div>
      <Footer />
    </div>
  );
}

// LitegraphCanvas.tsx
function LitegraphCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (!canvasRef.current) return;
    
    // Initialize your existing EditorInitializer
    const editor = new EditorInitializer();
    editor.createEditor(canvasRef.current);
  }, []);
  
  return <div ref={canvasRef} className="litegraph-container" />;
}
```

**Migration Effort:** 2-4 weeks (much less than full rewrite)

---

## Performance Comparison

### Canvas 2D (Litegraph) - Your Current Approach
- **Nodes:** 10k+ nodes possible with proper optimization
- **FPS:** 60fps with <500 visible nodes
- **Your optimizations:**
  - Conditional background rendering ✅
  - Native clearRect ✅
  - Viewport culling (only draw visible nodes)
  - Dirty region tracking
- **Bottleneck:** Rustworkx backend, not frontend rendering
- **Result:** More than fast enough for your use case

### React Flow
- **Nodes:** 1000-2000 max (per their docs)
- **FPS:** Drops below 30fps with 1000+ nodes
- **Why:** HTML div-based (slow DOM updates)
- **Result:** ❌ Does NOT meet your 10k+ requirement

### PixiJS (WebGL)
- **Nodes:** 50k+ objects possible
- **FPS:** 60fps even with 10k+ sprites
- **Trade-offs:**
  - Complex text rendering
  - Harder to integrate HTML UI
  - "Too flashy" concern valid
- **Result:** Overkill; complexity not justified

---

## Cost-Benefit Analysis

### Option 1: Migrate to React
- **Cost:** 6-12 months development + high risk
- **Benefit:** Component ecosystem (not needed for canvas)
- **ROI:** ❌ Negative - lose 6-12 months for minimal gain

### Option 2: Migrate to PixiJS
- **Cost:** 12-18 months development + learning curve
- **Benefit:** GPU rendering (not needed until 50k+ nodes)
- **ROI:** ❌ Negative - overkill for your use case

### Option 3: Enhance Litegraph
- **Cost:** 3-6 months for cloud features
- **Benefit:** Production-ready cloud SaaS in months, not years
- **ROI:** ✅ Positive - fastest time to market

### Option 4: Hybrid (Litegraph + React Chrome)
- **Cost:** 4-7 months (includes React chrome migration)
- **Benefit:** Keep Litegraph performance + React UI benefits
- **ROI:** ✅ Positive - best of both worlds with manageable risk

---

## Technical Considerations for Cloud

### Authentication
**Recommended:** Auth0, Firebase, or AWS Cognito
- JWT tokens in HTTP headers and WebSocket handshake
- Refresh tokens for long sessions
- SSO for enterprise customers

**Implementation:**
```python
# server/api/middleware.py
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials: HTTPBearer = Depends(security)):
    token = credentials.credentials
    # Verify JWT with Auth0/Firebase/Cognito
    user = await auth_service.verify(token)
    if not user:
        raise HTTPException(401)
    return user
```

### Database Schema (PostgreSQL)
```sql
-- users table (managed by Auth0/Firebase)
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    tier TEXT CHECK (tier IN ('free', 'pro', 'enterprise')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- workspaces (projects)
CREATE TABLE workspaces (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- graphs (your current JSON format)
CREATE TABLE graphs (
    id UUID PRIMARY KEY,
    workspace_id UUID REFERENCES workspaces(id),
    name TEXT,
    data JSONB,  -- Your current graph JSON
    version INT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- execution history
CREATE TABLE executions (
    id UUID PRIMARY KEY,
    graph_id UUID REFERENCES graphs(id),
    status TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT
);
```

### Deployment Architecture
```
                    ┌─────────────────┐
                    │   Load Balancer │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
         │ Web App │    │ Web App │   │ Web App │
         │ (FastAPI│    │ (FastAPI│   │ (FastAPI│
         │ + Vite) │    │ + Vite) │   │ + Vite) │
         └────┬────┘    └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
         │ Worker  │    │ Worker  │   │ Worker  │
         │ (Graph  │    │ (Graph  │   │ (Graph  │
         │ Execute)│    │ Execute)│   │ Execute)│
         └────┬────┘    └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │   Redis (Queue) │
                    └─────────────────┘
                             │
                    ┌────────▼────────┐
                    │   PostgreSQL    │
                    │   (User Data)   │
                    └─────────────────┘
```

### Scaling Strategy
1. **Horizontal Scaling:**
   - Web app instances (FastAPI + frontend) scale with traffic
   - Worker instances scale with execution load
   - Redis queue coordinates work distribution

2. **Vertical Scaling:**
   - Workers can have more CPU/RAM for heavy graphs
   - Database can scale with read replicas

3. **Caching:**
   - Redis for session state
   - CDN for static frontend assets
   - In-memory cache for frequently used graphs

---

## Migration Risk Assessment

### Risk: Migrating to React or PixiJS
- **Probability:** High
- **Impact:** Critical (6-18 months lost)
- **Mitigation:** Don't do it

### Risk: Enhancing Litegraph
- **Probability:** Low
- **Impact:** Minor (bugs in new features)
- **Mitigation:** 
  - Incremental rollout
  - Feature flags
  - Comprehensive testing
  - Keep existing functionality working

---

## Recommended Roadmap

### Month 1-2: Cloud Foundation
- [ ] Set up Docker container
- [ ] Deploy to cloud (AWS/GCP/Azure)
- [ ] Integrate Auth0/Firebase
- [ ] Set up PostgreSQL
- [ ] Migrate graph storage to cloud
- [ ] Add user workspaces

### Month 3-4: Multi-User Features
- [ ] User profiles
- [ ] Workspace management
- [ ] Graph sharing
- [ ] Permissions system
- [ ] Billing integration (Stripe)

### Month 5-6: Production Hardening
- [ ] Monitoring (Datadog, New Relic)
- [ ] Error tracking (Sentry)
- [ ] Load testing
- [ ] Security audit
- [ ] Documentation

### Month 7+: Advanced Features
- [ ] Real-time collaboration (if needed)
- [ ] Version history
- [ ] API for external integrations
- [ ] Mobile app (React Native reusing backend)
- [ ] Enterprise features

---

## Conclusion

### DO: Enhance Your Litegraph Fork ✅

**You've built a solid, performant, production-ready node graph editor.** Don't throw it away to chase React or PixiJS. Your Litegraph fork is:
- Modern (TypeScript, Vite)
- Fast (10k+ nodes capable)
- Maintainable (service architecture)
- Production-ready (build/deploy works)

**Focus on what matters:**
- Authentication
- Cloud deployment
- Multi-user features
- Billing
- Enterprise features

**Timeline:** 3-6 months to launch cloud version

### DON'T: Migrate to React/PixiJS ❌

**Reasons:**
- 6-18 months lost
- High risk of failure
- No performance benefit
- React/PixiJS not optimized for node graphs
- Your current solution is better

### CONSIDER: Hybrid Approach (Litegraph + React Chrome) 🤔

**If you want React benefits:**
- Keep Litegraph canvas (performance)
- Use React for UI chrome (sidebars, modals)
- Best of both worlds
- Gradual migration possible
- +1-2 months to timeline

---

## Questions to Consider

1. **What's more important: Time to market or React ecosystem?**
   - Time to market → Enhance Litegraph
   - React ecosystem → Hybrid approach

2. **Do you need real-time collaboration?**
   - Yes → Add WebSocket sync to Litegraph
   - No → Simple cloud storage sufficient

3. **What's your team's expertise?**
   - Strong TypeScript → Enhance Litegraph
   - Strong React → Hybrid approach
   - Learning curve okay → Any option

4. **What's your budget?**
   - 3-6 months → Enhance Litegraph
   - 6-12 months → Hybrid approach
   - 12-18 months → Full rewrite (not recommended)

---

## Final Recommendation

**Enhance your Litegraph fork for cloud.** You've already done the hard work. Your codebase is excellent. Focus on:
1. Authentication (Auth0)
2. Cloud deployment (Docker + AWS/GCP)
3. Multi-user features (PostgreSQL)
4. Billing (Stripe)
5. Polish (better UX, mobile support)

**Timeline:** 3-6 months to launch

**Risk:** Low

**ROI:** High

**Don't waste 6-18 months rewriting what already works.**

---

## Additional Resources

### Litegraph Enhancement Examples
- **ComfyUI:** Similar stack, millions of users
- **Node-RED:** Canvas-based, cloud-deployed
- **Retool:** Hybrid (React + Canvas)

### Cloud Deployment Tools
- **Docker:** Containerization
- **AWS ECS / GCP Cloud Run:** Managed containers
- **Auth0 / Firebase:** Authentication
- **PostgreSQL / Supabase:** Database
- **Stripe:** Billing

### If You Still Want React Chrome
- **Figma's architecture:** Canvas + React chrome
- **VSCode:** Electron (similar hybrid approach)
- **Notion:** Rich editor + React UI

---

**Let me know if you need help with:**
- Cloud deployment strategy
- Authentication implementation
- Database schema design
- Hybrid React + Litegraph architecture
- Performance optimization
- Scaling strategy

Your current codebase is a strong foundation. Build on it, don't rebuild it.

