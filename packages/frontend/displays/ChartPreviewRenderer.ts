import {
  BaseOutputDisplayRenderer,
  type RenderBounds,
  type Point,
} from './OutputDisplayRenderer';

/**
 * Chart data types (matching backend output)
 */
interface CandlestickData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface LineSeriesData {
  time: number;
  value: number;
}

interface OverlayConfig {
  id: string;
  label: string;
  type: 'SMA' | 'EMA';
  period: number;
  color: string;
  data: LineSeriesData[];
}

interface ChartConfig {
  symbol: string;
  assetClass: string;
  candlesticks: CandlestickData[];
  overlays: OverlayConfig[];
  horizontalLines: Array<{ price: number; color: string; lineStyle: string; label?: string }>;
  metadata: {
    barCount: number;
    startTime: number;
    endTime: number;
    priceRange: { min: number; max: number };
  };
}

/**
 * Chart preview renderer for mini candlestick/line charts.
 *
 * Features:
 * - Mini candlestick preview
 * - Symbol info display
 * - Click to open modal
 * - Multi-symbol selector
 *
 * Extracted from OHLCVChartNodeUI.ts
 */
export class ChartPreviewRenderer extends BaseOutputDisplayRenderer {
  readonly type = 'chart-preview';

  private charts: Record<string, ChartConfig> = {};
  private selectedSymbol: string | null = null;

  // Button bounds for click detection
  private viewButtonBounds: RenderBounds | null = null;

  draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    if (!ctx || typeof ctx.fillRect !== 'function') return;

    const { x, y, width, height } = bounds;

    // Background
    ctx.fillStyle = '#0f1419';
    ctx.fillRect(x, y, width, height);

    // Border
    ctx.strokeStyle = 'rgba(75, 85, 99, 0.3)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, width - 1, height - 1);

    const symbols = Object.keys(this.charts);

    if (symbols.length === 0) {
      ctx.fillStyle = 'rgba(156, 163, 175, 0.5)';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('No chart data', x + width / 2, y + height / 2);
      return;
    }

    const chart = this.selectedSymbol
      ? this.charts[this.selectedSymbol]
      : this.charts[symbols[0]!];
    if (!chart) return;

    // Header with symbol info
    ctx.fillStyle = '#e5e7eb';
    ctx.font = 'bold 11px Arial';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`${chart.symbol} (${chart.assetClass})`, x + 8, y + 6);

    // Stats
    ctx.fillStyle = 'rgba(156, 163, 175, 0.8)';
    ctx.font = '10px Arial';
    const statsY = y + 20;
    ctx.fillText(`${chart.metadata.barCount} bars`, x + 8, statsY);

    const priceRange = `$${chart.metadata.priceRange.min.toFixed(2)} - $${chart.metadata.priceRange.max.toFixed(2)}`;
    ctx.fillText(priceRange, x + 8, statsY + 12);

    if (chart.overlays.length > 0) {
      const overlayText = chart.overlays.map(o => o.label).join(', ');
      ctx.fillText(`Overlays: ${overlayText}`, x + 8, statsY + 24);
    }

    // Mini candlestick chart
    const chartY = y + 52;
    const chartH = height - 80;
    const chartW = width - 16;

    if (chart.candlesticks.length > 0 && chartH > 20) {
      this.drawMiniCandlesticks(ctx, chart.candlesticks, x + 8, chartY, chartW, chartH, chart.metadata.priceRange);
    }

    // View Chart button
    if (this.options.modalEnabled !== false) {
      const btnH = 24;
      const btnY = y + height - btnH - 4;
      const btnW = 80;
      const btnX = x + width / 2 - btnW / 2;

      this.viewButtonBounds = { x: btnX, y: btnY, width: btnW, height: btnH };

      ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
      ctx.beginPath();
      ctx.roundRect(btnX, btnY, btnW, btnH, 4);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 10px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('View Chart', btnX + btnW / 2, btnY + btnH / 2);
    }

    // Symbol count indicator
    if (symbols.length > 1 && this.options.symbolSelector !== false) {
      ctx.fillStyle = 'rgba(156, 163, 175, 0.6)';
      ctx.font = '9px Arial';
      ctx.textAlign = 'right';
      ctx.fillText(`${symbols.length} symbols`, x + width - 8, y + 8);
    }
  }

  private drawMiniCandlesticks(
    ctx: CanvasRenderingContext2D,
    candlesticks: CandlestickData[],
    x: number,
    y: number,
    width: number,
    height: number,
    priceRange: { min: number; max: number }
  ): void {
    const { min, max } = priceRange;
    const range = max - min || 1;

    // Show last N candles that fit
    const candleWidth = 3;
    const candleSpacing = 1;
    const maxCandles = Math.floor(width / (candleWidth + candleSpacing));
    const displayCandles = candlesticks.slice(-maxCandles);

    const scaleY = (price: number) => y + height - ((price - min) / range) * height;

    displayCandles.forEach((candle, i) => {
      const cx = x + i * (candleWidth + candleSpacing);
      const isUp = candle.close >= candle.open;
      const color = isUp ? '#26a69a' : '#ef5350';

      // Wick
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx + candleWidth / 2, scaleY(candle.high));
      ctx.lineTo(cx + candleWidth / 2, scaleY(candle.low));
      ctx.stroke();

      // Body
      const bodyTop = scaleY(Math.max(candle.open, candle.close));
      const bodyBottom = scaleY(Math.min(candle.open, candle.close));
      const bodyHeight = Math.max(1, bodyBottom - bodyTop);

      ctx.fillStyle = color;
      ctx.fillRect(cx, bodyTop, candleWidth, bodyHeight);
    });
  }

  updateFromResult(result: unknown): void {
    // Expect { charts: { symbol: ChartConfig } }
    const resultObj = result as Record<string, unknown>;
    this.charts = (resultObj?.charts as Record<string, ChartConfig>) ?? {};

    // Select first symbol by default
    const symbols = Object.keys(this.charts);
    if (symbols.length > 0 && !this.selectedSymbol) {
      this.selectedSymbol = symbols[0] ?? null;
    }

    this.setDirtyCanvas();
  }

  onMouseDown(event: MouseEvent, pos: Point, _canvas: unknown): boolean {
    // Check if click is on View Chart button
    if (this.viewButtonBounds && this.options.modalEnabled !== false) {
      const { x, y, width, height } = this.viewButtonBounds;
      if (pos.x >= x && pos.x <= x + width && pos.y >= y && pos.y <= y + height) {
        this.openChartModal();
        return true;
      }
    }
    return false;
  }

  private openChartModal(): void {
    const symbols = Object.keys(this.charts);
    if (symbols.length === 0) return;

    const chart = this.selectedSymbol
      ? this.charts[this.selectedSymbol]
      : this.charts[symbols[0]!];
    if (!chart) return;

    // Dispatch custom event for modal opening
    const modalEvent = new CustomEvent('open-chart-modal', {
      detail: {
        chart,
        allCharts: this.charts,
      }
    });
    window.dispatchEvent(modalEvent);
  }
}
