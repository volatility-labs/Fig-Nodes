# Troubleshooting Guide

## Common Issues & Solutions

### Issue 1: CSS Import Errors

**Symptoms:**
```
Unable to resolve `@import "../frontend/..."` from /Users/steve/Fig-Nodes/frontend-react/src
```

**Solution:**
✅ **Fixed!** CSS import paths updated to use `../../frontend/` instead of `../frontend/`

---

### Issue 2: Editor Not Loading

**Symptoms:**
- Loading spinner shows forever
- Error message: "Failed to initialize editor"
- Console shows import errors

**Possible Causes & Solutions:**

#### A. Backend Not Running
```bash
# Terminal 1: Make sure backend is running
cd /Users/steve/Fig-Nodes
uv run python main.py --dev
```
Backend should be on `http://localhost:8000`

#### B. Litegraph Build Missing
```bash
# Build litegraph if not already built
cd frontend/fignode-litegraph.js
yarn install
yarn build
```

#### C. Frontend Dependencies Missing
```bash
# In frontend-react directory
yarn install
```

---

### Issue 3: "Execution Failed" Error

**Symptoms:**
- Editor loads but Execute button doesn't work
- Console error about execution

**Solution:**
Make sure backend is running and WebSocket connection is established.

Check console for:
```
✅ WebSocket connected
```

If you see:
```
❌ WebSocket connection failed
```

Then backend isn't running or port is wrong.

---

### Issue 4: Scrolling Not Working

**Symptoms:**
- Can't pan/zoom canvas
- Mouse wheel doesn't work

**Check:**
1. Is the canvas actually loaded? (should see grid background)
2. Try clicking on canvas first to focus it
3. Check console for errors during initialization

---

### Issue 5: Nodes Not Visible After Adding

**Symptoms:**
- Click node in sidebar, nothing happens
- Or node added but can't find it

**Solution:**
✅ **Fixed!** Nodes now:
- Appear at viewport center
- Get automatically selected
- Viewport pans to show them

**Manual Fix:**
Click "Reset" button or "🔍 Fit View" button to see all nodes.

---

## Debug Mode

### Check Browser Console

Open browser DevTools (F12) and look for:

**Good signs:**
```
✅ Litegraph patches loaded
✅ EditorInitializer loaded
✅ Litegraph editor initialized in React wrapper
✅ WebSocket connected
```

**Bad signs:**
```
❌ Failed to initialize Litegraph editor: ...
❌ Failed to load EditorInitializer: ...
❌ WebSocket connection failed
```

---

## Quick Check List

Before asking for help, verify:

- [ ] Backend is running (`uv run python main.py --dev`)
- [ ] Backend is on port 8000
- [ ] React wrapper is running (`yarn dev` in frontend-react/)
- [ ] React wrapper is on port 5174
- [ ] Browser console shows no red errors
- [ ] Litegraph is built (`frontend/fignode-litegraph.js/dist/` exists)
- [ ] You're visiting `http://localhost:5174` (not 5173)

---

## Still Not Working?

### Get Detailed Logs

1. Open browser console (F12)
2. Reload page (Cmd+R or Ctrl+R)
3. Copy all console output
4. Look for the first error

### Common Error Patterns

**Error: "Cannot find module '@legacy/...'"**
```
Solution: Use relative imports instead:
import('../../frontend/services/EditorInitializer')
```

**Error: "graph is undefined"**
```
Solution: Editor not fully initialized. Check loading state.
```

**Error: "WebSocket connection to 'ws://localhost:8000/...' failed"**
```
Solution: Backend not running. Start with:
uv run python main.py --dev
```

---

## Compare with Old Frontend

If React wrapper isn't working, you can always use the old frontend:

```bash
# Just run backend (auto-starts old frontend on 5173)
uv run python main.py --dev

# Visit http://localhost:5173
```

This helps isolate whether the issue is:
- React wrapper specific (works on 5173, broken on 5174)
- General backend issue (broken on both)

---

## Development vs Production

### Development (Current)
```bash
# Terminal 1: Backend
uv run python main.py --dev

# Terminal 2: React wrapper
cd frontend-react
yarn dev
```

### Production (Future)
```bash
# Build React wrapper
cd frontend-react
yarn build

# Deploy built dist/ with backend
```

---

## Environment Check

Make sure you have:
```bash
# Check Node version (need 20+)
node --version

# Check yarn
yarn --version

# Check Python (need 3.11+)
python --version

# Check uv
uv --version
```

---

## Clean Start (Nuclear Option)

If nothing works, try a clean start:

```bash
# 1. Stop all servers (Ctrl+C in all terminals)

# 2. Clean frontend-react
cd frontend-react
rm -rf node_modules yarn.lock
yarn install

# 3. Clean litegraph build
cd ../frontend/fignode-litegraph.js
rm -rf node_modules yarn.lock dist
yarn install
yarn build

# 4. Restart everything
cd ../..
uv run python main.py --dev

# In another terminal:
cd frontend-react
yarn dev
```

---

## Report Issues

If you're still stuck, provide:

1. **Console output** (copy from browser DevTools)
2. **Terminal output** (from both backend and React wrapper)
3. **What you did** (steps to reproduce)
4. **What you expected** vs **what happened**
5. **Environment** (Mac/Linux/Windows, Node version, Python version)

Example good bug report:
```
1. Started backend: `uv run python main.py --dev` - works
2. Started React wrapper: `cd frontend-react && yarn dev` - works
3. Visited http://localhost:5174
4. Expected: Editor loads
5. Actual: Loading spinner forever
6. Console error: "Failed to load EditorInitializer: Cannot find module"
7. Environment: macOS, Node 20.10, Python 3.11
```

This makes it much easier to help!

