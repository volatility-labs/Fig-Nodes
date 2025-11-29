# Performance Profiling Guide

## Overview

The Performance Profiler tracks key metrics to identify bottlenecks in graph rendering and data processing. It helps determine whether lag is caused by:
- Canvas rendering (too many redraws)
- Data processing (JSON.stringify, serialization)
- Memory usage (garbage collection pauses)
- Frame drops (rendering taking too long)

## Usage

### Console Commands

The profiler is automatically available in the browser console:

```javascript
// Start profiling
startProfiling()

// Stop profiling and see results
stopProfiling()

// Get current stats without stopping
getProfilingStats()

// Export profiling data as JSON file
exportProfilingData()
```

### Example Workflow

1. **Before starting a scan:**
   ```javascript
   startProfiling()
   ```

2. **Run your scan** (let it complete)

3. **After scan completes:**
   ```javascript
   stopProfiling()
   ```

4. **Review the results** - The console will show:
   - Frame performance (average, max, min frame times)
   - Dropped frames count
   - Render call counts
   - Node update counts
   - Memory usage
   - Custom metric timings

5. **Export data for analysis:**
   ```javascript
   exportProfilingData()
   ```

## Metrics Tracked

### Frame Metrics
- **Frame Time**: Time between frames (target: <16.67ms for 60fps)
- **Dropped Frames**: Frames taking longer than 16.67ms
- **Render Calls**: Number of canvas redraws per frame
- **Node Updates**: Number of nodes updated per frame

### Custom Metrics
- **handleDataMessage**: Time to process WebSocket data messages
- **updateDisplay**: Time to update individual node displays
- **autosave**: Time to serialize and save graph state

### Memory Metrics
- **Peak Memory Usage**: Maximum JavaScript heap size during profiling

## Interpreting Results

### Good Performance
- Average frame time: < 10ms
- Dropped frames: < 5% of total frames
- Memory usage: Stable (no large spikes)

### Performance Issues

**High Frame Times (>16ms average)**
- Likely cause: Too many render calls or expensive rendering operations
- Solution: Implement viewport culling, reduce redraws

**Many Dropped Frames (>10%)**
- Likely cause: Heavy computation blocking main thread
- Solution: Optimize data processing, use Web Workers

**High Memory Usage**
- Likely cause: Large objects not being garbage collected
- Solution: Clear unused data, implement object pooling

**Slow handleDataMessage**
- Likely cause: Processing too many node updates at once
- Solution: Batch updates, throttle processing

**Slow updateDisplay**
- Likely cause: JSON.stringify on large objects
- Solution: Skip serialization for non-displayed nodes (already implemented)

**Slow autosave**
- Likely cause: Large graph serialization
- Solution: Optimize serialization, increase interval

## Next Steps

Based on profiling results:

1. **If rendering is the bottleneck** → Consider PIXI.js migration
2. **If data processing is the bottleneck** → Optimize serialization/deserialization
3. **If memory is the issue** → Implement better cleanup and object pooling
4. **If frame drops are the issue** → Implement viewport culling and LOD

