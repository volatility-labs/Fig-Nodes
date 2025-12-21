# Logging in React Wrapper - What You Should See

## 🎯 Quick Answer

**You're right!** There's **no terminal logging** for the React wrapper frontend. Here's what logs where:

| What | Where to See Logs | Why |
|------|-------------------|-----|
| **Backend** | Terminal 1 (backend) | Python FastAPI logs |
| **Old Frontend** | Terminal 1 (Vite dev server) | Bundled with backend |
| **React Wrapper** | Browser Console (F12) | Runs in browser, not terminal |

---

## 🔍 Where to See React Wrapper Logs

### Browser Console (F12)

**This is where ALL React wrapper logs appear:**

1. Press **F12** (or Cmd+Option+I on Mac)
2. Click **Console** tab
3. You'll see:
   ```
   🔄 Loading Litegraph patches...
   ✅ Litegraph patches loaded
   📦 Creating editor instance...
   ✅ Litegraph editor initialized
   ```

**Why browser console?**
- React wrapper is a **client-side app**
- Runs entirely in the browser
- No server-side rendering

---

## 📊 What Shows in Each Terminal

### Terminal 1 (Backend):
```bash
uv run python main.py --dev

# Shows:
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     127.0.0.1:64691 - "GET /api/v1/nodes HTTP/1.1" 200 OK
INFO:     127.0.0.1:64742 - "GET /api/nodes HTTP/1.1" 404 Not Found
```

**What you see:**
- ✅ Backend startup
- ✅ API requests from frontend
- ✅ WebSocket connections
- ✅ Graph execution logs

**What you DON'T see:**
- ❌ React component rendering
- ❌ Frontend state changes
- ❌ Browser events

---

### Terminal 2 (React Wrapper):
```bash
yarn dev

# Shows:
VITE v5.4.21  ready in 139 ms
➜  Local:   http://localhost:5174/
```

**What you see:**
- ✅ Vite dev server started
- ✅ Port number (5174)
- ✅ Hot module replacement (HMR) updates
- ❌ **No app-level logs** (those go to browser console)

**This is normal!** Vite just serves the app. The app logs to browser console.

---

## 🎨 Visual Guide: Where Logs Appear

```
┌─────────────────────────────────────────────────────┐
│  Browser (http://localhost:5174)                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  React App                                    │  │
│  │  - Component rendering                        │  │
│  │  - State updates                              │  │
│  │  - User interactions                          │  │
│  │                                               │  │
│  │  Logs go to: Browser Console (F12) ← HERE!   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                         ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────┐
│  Backend (Terminal 1)                                │
│  - API requests                                      │
│  - Graph execution                                   │
│  - Database operations                               │
│  │                                                   │
│  Logs go to: Terminal 1 ← HERE!                     │
└─────────────────────────────────────────────────────┘
```

---

## 🔧 Debugging Workflow

### Problem: "Editor not loading"

**Step 1: Check Browser Console (F12)**
```
✅ Look for errors in red
✅ Check what step it's stuck on
✅ Copy error messages
```

**Step 2: Check Backend Terminal**
```
✅ Is backend running?
✅ Are API requests succeeding (200 OK)?
✅ Any Python errors?
```

**Step 3: Check React Wrapper Terminal**
```
✅ Is Vite running?
✅ Port 5174 available?
✅ Any HMR errors?
```

---

## 📱 Production vs Development

### Development (Now)
- **Frontend logs:** Browser console
- **Backend logs:** Terminal
- **Vite logs:** Separate terminal

### Production (Future)
- **Frontend logs:** Browser console (same!)
- **Backend logs:** Server logs (CloudWatch, Datadog, etc.)
- **No Vite:** Built bundle served by backend

**Frontend ALWAYS logs to browser console** - this never changes!

---

## 🎯 Common Questions

### Q: "Why don't I see React logs in terminal?"
**A:** React runs in the browser, not in Node.js. Browser apps log to browser console.

### Q: "How do I debug the React wrapper?"
**A:** Open browser DevTools (F12), use React DevTools extension, check Console tab.

### Q: "Can I see React logs in terminal?"
**A:** Not easily. You'd need a tool like `debug` package or custom logging service. Browser console is the standard way.

### Q: "What about the old frontend (port 5173)?"
**A:** Same! It also logs to browser console. Terminal only shows Vite server logs.

---

## 🎁 Pro Tips

### Tip 1: Keep Browser Console Open
```
Press F12 and dock it to the side
Always see logs while developing
```

### Tip 2: Filter Console Logs
```
In browser console, type: LitegraphEditor
Shows only editor-related logs
```

### Tip 3: Use React DevTools
```
Install: https://reactjs.org/link/react-devtools
See component state, props, and renders
```

### Tip 4: Backend Correlation
```
Backend shows API calls with timestamps
Match browser console logs to backend logs
Example:
  Browser: "Fetching nodes..."
  Backend: "GET /api/v1/nodes 200 OK"
```

---

## 🚀 What You Should Monitor

### During Development

**Browser Console (F12):**
- ✅ Component initialization
- ✅ User interactions
- ✅ API call results
- ✅ Errors and warnings

**Backend Terminal:**
- ✅ API requests (200 OK = good!)
- ✅ WebSocket connections
- ✅ Graph execution progress
- ✅ Python errors

**React Wrapper Terminal:**
- ✅ HMR updates (shows file changes)
- ✅ Port availability
- ✅ Build errors (rare)

---

## 📖 Example: Full Logging Picture

### When You Load the Page

**Browser Console (F12):**
```
🔄 Loading Litegraph patches...
✅ Litegraph patches loaded
📦 Creating editor instance...
Fetching nodes from /api/v1/nodes
✅ Got 55 node types
✅ Editor initialized
```

**Backend Terminal 1:**
```
INFO: 127.0.0.1 - "GET /api/v1/nodes HTTP/1.1" 200 OK
INFO: 127.0.0.1 - "GET /examples/default-graph.json" 200 OK
INFO: WebSocket connection opened
```

**React Wrapper Terminal 2:**
```
(shows nothing - this is normal!)
```

---

## 🎓 Summary

**Key Takeaway:** 
- Frontend logs → **Browser Console (F12)**
- Backend logs → **Terminal 1**
- Vite server logs → **Terminal 2** (minimal)

**This is standard for web apps!** Every React app works this way. The terminal is for the server, the browser console is for the client.

---

## 🔗 Useful Links

- **React DevTools:** https://reactjs.org/link/react-devtools
- **Chrome DevTools:** https://developer.chrome.com/docs/devtools/
- **Debugging React:** https://react.dev/learn/debugging

---

**Remember: Open Browser Console (F12) to see React logs!** 🚀

