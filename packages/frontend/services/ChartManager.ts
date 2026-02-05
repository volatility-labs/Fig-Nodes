// ChartManager - Handles chart modal rendering with Lightweight Charts
// Follows the DialogManager pattern for modal management

import { ServiceRegistry } from './ServiceRegistry';
import { createChart, CrosshairMode, LineStyle, ColorType, IChartApi } from 'lightweight-charts';

// Types matching backend ChartConfig
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

interface HorizontalLine {
    price: number;
    color: string;
    lineStyle: 'solid' | 'dashed' | 'dotted';
    label?: string;
}

interface ChartConfig {
    symbol: string;
    assetClass: string;
    candlesticks: CandlestickData[];
    overlays: OverlayConfig[];
    horizontalLines: HorizontalLine[];
    metadata: {
        barCount: number;
        startTime: number;
        endTime: number;
        priceRange: { min: number; max: number };
    };
}

interface ChartModalEventDetail {
    chart: ChartConfig;
    allCharts: Record<string, ChartConfig>;
}

export class ChartManager {
    private modalOverlay: HTMLDivElement | null = null;
    private chartInstance: IChartApi | null = null;
    private currentSymbol: string | null = null;
    private allCharts: Record<string, ChartConfig> = {};
    private resizeObserver: ResizeObserver | null = null;

    constructor(_serviceRegistry: ServiceRegistry) {
        this.setupEventListeners();
    }

    private setupEventListeners(): void {
        window.addEventListener('open-chart-modal', ((event: CustomEvent<ChartModalEventDetail>) => {
            this.openModal(event.detail.chart, event.detail.allCharts);
        }) as EventListener);
    }

    openModal(chart: ChartConfig, allCharts: Record<string, ChartConfig>): void {
        this.allCharts = allCharts;
        this.currentSymbol = chart.symbol;

        // Remove existing modal if any
        this.closeModal();

        // Create modal overlay
        this.modalOverlay = document.createElement('div');
        this.modalOverlay.className = 'chart-modal-overlay';

        const modal = document.createElement('div');
        modal.className = 'chart-modal';

        // Header with symbol selector and close button
        const header = document.createElement('div');
        header.className = 'chart-modal-header';

        const symbolSelector = this.createSymbolSelector(allCharts);
        header.appendChild(symbolSelector);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'chart-modal-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.onclick = () => this.closeModal();
        header.appendChild(closeBtn);

        // Chart container
        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-modal-container';
        chartContainer.id = 'lightweight-chart-container';

        // Stats footer
        const footer = document.createElement('div');
        footer.className = 'chart-modal-footer';
        footer.id = 'chart-modal-stats';

        modal.appendChild(header);
        modal.appendChild(chartContainer);
        modal.appendChild(footer);
        this.modalOverlay.appendChild(modal);
        document.body.appendChild(this.modalOverlay);

        // Close on overlay click
        this.modalOverlay.addEventListener('click', (e) => {
            if (e.target === this.modalOverlay) {
                this.closeModal();
            }
        });

        // Close on Escape key
        const escHandler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                this.closeModal();
                window.removeEventListener('keydown', escHandler);
            }
        };
        window.addEventListener('keydown', escHandler);

        // Render chart
        this.renderChart(chart, chartContainer);
        this.updateStats(chart);
    }

    private createSymbolSelector(allCharts: Record<string, ChartConfig>): HTMLElement {
        const symbols = Object.keys(allCharts);

        if (symbols.length <= 1) {
            const label = document.createElement('span');
            label.className = 'chart-modal-symbol-label';
            label.textContent = this.currentSymbol || 'Chart';
            return label;
        }

        const select = document.createElement('select');
        select.className = 'chart-modal-symbol-select';

        symbols.forEach(symbol => {
            const option = document.createElement('option');
            option.value = symbol;
            option.textContent = symbol;
            option.selected = symbol === this.currentSymbol;
            select.appendChild(option);
        });

        select.addEventListener('change', () => {
            const newSymbol = select.value;
            const newChart = this.allCharts[newSymbol];
            if (newChart) {
                this.currentSymbol = newSymbol;
                const container = document.getElementById('lightweight-chart-container');
                if (container) {
                    this.renderChart(newChart, container);
                    this.updateStats(newChart);
                }
            }
        });

        return select;
    }

    private renderChart(chartConfig: ChartConfig, container: HTMLElement): void {
        // Clear existing chart
        if (this.chartInstance) {
            this.chartInstance.remove();
            this.chartInstance = null;
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        container.innerHTML = '';

        // Create chart with dark theme
        const chart = createChart(container, {
            width: container.clientWidth,
            height: container.clientHeight,
            layout: {
                background: { type: ColorType.Solid, color: '#0f1419' },
                textColor: '#d1d4dc',
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 0.5)' },
                horzLines: { color: 'rgba(42, 46, 57, 0.5)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: 'rgba(197, 203, 206, 0.3)',
            },
            timeScale: {
                borderColor: 'rgba(197, 203, 206, 0.3)',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        this.chartInstance = chart;

        // Add candlestick series
        const candlestickSeries = chart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderDownColor: '#ef5350',
            borderUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            wickUpColor: '#26a69a',
        });

        // Convert data format for Lightweight Charts (time as UTCTimestamp)
        const candleData = chartConfig.candlesticks.map(c => ({
            time: c.time as unknown as import('lightweight-charts').UTCTimestamp,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

        candlestickSeries.setData(candleData);

        // Add overlay line series
        for (const overlay of chartConfig.overlays) {
            const lineSeries = chart.addLineSeries({
                color: overlay.color,
                lineWidth: 2,
                title: overlay.label,
            });

            const lineData = overlay.data.map(d => ({
                time: d.time as unknown as import('lightweight-charts').UTCTimestamp,
                value: d.value,
            }));

            lineSeries.setData(lineData);
        }

        // Add horizontal lines (price levels)
        for (const hLine of chartConfig.horizontalLines) {
            candlestickSeries.createPriceLine({
                price: hLine.price,
                color: hLine.color,
                lineWidth: 1,
                lineStyle: this.getLineStyle(hLine.lineStyle),
                axisLabelVisible: true,
                title: hLine.label || '',
            });
        }

        // Fit content
        chart.timeScale().fitContent();

        // Handle resize
        this.resizeObserver = new ResizeObserver(() => {
            if (this.chartInstance && container.clientWidth > 0 && container.clientHeight > 0) {
                this.chartInstance.resize(container.clientWidth, container.clientHeight);
            }
        });
        this.resizeObserver.observe(container);
    }

    private getLineStyle(style: string): typeof LineStyle[keyof typeof LineStyle] {
        switch (style) {
            case 'dashed':
                return LineStyle.Dashed;
            case 'dotted':
                return LineStyle.Dotted;
            default:
                return LineStyle.Solid;
        }
    }

    private updateStats(chart: ChartConfig): void {
        const footer = document.getElementById('chart-modal-stats');
        if (!footer) return;

        const { metadata, assetClass } = chart;
        const startDate = new Date(metadata.startTime * 1000).toLocaleDateString();
        const endDate = new Date(metadata.endTime * 1000).toLocaleDateString();

        footer.innerHTML = `
            <span class="chart-stat">
                <span class="chart-stat-label">Asset Class:</span>
                <span class="chart-stat-value">${assetClass}</span>
            </span>
            <span class="chart-stat">
                <span class="chart-stat-label">Bars:</span>
                <span class="chart-stat-value">${metadata.barCount}</span>
            </span>
            <span class="chart-stat">
                <span class="chart-stat-label">Range:</span>
                <span class="chart-stat-value">${startDate} - ${endDate}</span>
            </span>
            <span class="chart-stat">
                <span class="chart-stat-label">Price:</span>
                <span class="chart-stat-value">$${metadata.priceRange.min.toFixed(2)} - $${metadata.priceRange.max.toFixed(2)}</span>
            </span>
        `;
    }

    closeModal(): void {
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }

        if (this.chartInstance) {
            this.chartInstance.remove();
            this.chartInstance = null;
        }

        if (this.modalOverlay && this.modalOverlay.parentNode) {
            this.modalOverlay.parentNode.removeChild(this.modalOverlay);
            this.modalOverlay = null;
        }

        this.currentSymbol = null;
        this.allCharts = {};
    }
}
