import { useState, useEffect, useRef } from 'react';
import './WatchlistPanel.css';

interface WatchlistItem {
  symbol: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  volume: number | null;
  assetClass: 'stocks' | 'crypto';
  lastUpdate: number;
}

interface WatchlistPanelProps {
  editor: any; // EditorInstance | null - keeping simple for now
}

type SortColumn = 'symbol' | 'price' | 'change' | 'changePercent' | 'volume' | null;
type SortDirection = 'asc' | 'desc';

export function WatchlistPanel({ editor }: WatchlistPanelProps) {
  const [activeTab, setActiveTab] = useState<'stocks' | 'crypto'>('stocks');
  const [stocks, setStocks] = useState<WatchlistItem[]>([]);
  const [crypto, setCrypto] = useState<WatchlistItem[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newSymbol, setNewSymbol] = useState('');
  const [sortColumn, setSortColumn] = useState<SortColumn>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const stocksRef = useRef<WatchlistItem[]>([]);
  const cryptoRef = useRef<WatchlistItem[]>([]);
  const updateBatchRef = useRef<Map<string, WatchlistItem>>(new Map());
  const batchTimeoutRef = useRef<number | null>(null);
  const tableBodyRef = useRef<HTMLDivElement>(null);

  // Default watchlist symbols
  const defaultStocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX'];
  const defaultCrypto = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'ADAUSD', 'DOTUSD', 'MATICUSD'];

  // Load watchlist from localStorage or use defaults
  useEffect(() => {
    const loadWatchlist = () => {
      const savedStocks = localStorage.getItem('watchlist_stocks');
      const savedCrypto = localStorage.getItem('watchlist_crypto');

      if (savedStocks) {
        try {
          const parsed = JSON.parse(savedStocks);
          const loadedStocks: WatchlistItem[] = parsed.map((s: string) => ({
            symbol: s,
            price: null,
            change: null,
            changePercent: null,
            volume: null,
            assetClass: 'stocks' as const,
            lastUpdate: Date.now(),
          }));
          setStocks(loadedStocks);
          stocksRef.current = loadedStocks;
        } catch {
          // Fallback to defaults
          const initialStocks: WatchlistItem[] = defaultStocks.map(symbol => ({
            symbol,
            price: null,
            change: null,
            changePercent: null,
            volume: null,
            assetClass: 'stocks',
            lastUpdate: Date.now(),
          }));
          setStocks(initialStocks);
          stocksRef.current = initialStocks;
        }
      } else {
        const initialStocks: WatchlistItem[] = defaultStocks.map(symbol => ({
          symbol,
          price: null,
          change: null,
          changePercent: null,
          volume: null,
          assetClass: 'stocks',
          lastUpdate: Date.now(),
        }));
        setStocks(initialStocks);
        stocksRef.current = initialStocks;
      }

      if (savedCrypto) {
        try {
          const parsed = JSON.parse(savedCrypto);
          const loadedCrypto: WatchlistItem[] = parsed.map((s: string) => ({
            symbol: s,
            price: null,
            change: null,
            changePercent: null,
            volume: null,
            assetClass: 'crypto' as const,
            lastUpdate: Date.now(),
          }));
          setCrypto(loadedCrypto);
          cryptoRef.current = loadedCrypto;
        } catch {
          // Fallback to defaults
          const initialCrypto: WatchlistItem[] = defaultCrypto.map(symbol => ({
            symbol,
            price: null,
            change: null,
            changePercent: null,
            volume: null,
            assetClass: 'crypto',
            lastUpdate: Date.now(),
          }));
          setCrypto(initialCrypto);
          cryptoRef.current = initialCrypto;
        }
      } else {
        const initialCrypto: WatchlistItem[] = defaultCrypto.map(symbol => ({
          symbol,
          price: null,
          change: null,
          changePercent: null,
          volume: null,
          assetClass: 'crypto',
          lastUpdate: Date.now(),
        }));
        setCrypto(initialCrypto);
        cryptoRef.current = initialCrypto;
      }
    };

    loadWatchlist();
  }, []);

  // Save watchlist to localStorage whenever it changes
  useEffect(() => {
    stocksRef.current = stocks;
    // Always save, even if empty (to persist removals)
    const symbols = stocks.map(s => s.symbol);
    localStorage.setItem('watchlist_stocks', JSON.stringify(symbols));
  }, [stocks]);

  useEffect(() => {
    cryptoRef.current = crypto;
    // Always save, even if empty (to persist removals)
    const symbols = crypto.map(s => s.symbol);
    localStorage.setItem('watchlist_crypto', JSON.stringify(symbols));
  }, [crypto]);

  // WebSocket connection management
  useEffect(() => {
    const connectWebSocket = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const backendHost = window.location.hostname;
      const wsUrl = `${protocol}//${backendHost}${window.location.port === '8000' ? '' : ':8000'}/api/v1/watchlist/stream`;

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
          console.log('Watchlist WebSocket connected');
          
          // Send subscription with current symbols from refs
          subscribeToSymbols.current(ws, stocksRef.current, cryptoRef.current);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'update') {
              // Batch updates to reduce re-renders and prevent flickering
              const key = `${data.assetClass}:${data.symbol}`;
              updateBatchRef.current.set(key, {
                symbol: data.symbol,
                price: data.price,
                change: data.change,
                changePercent: data.changePercent,
                volume: data.volume,
                assetClass: data.assetClass,
                lastUpdate: Date.now(),
              });

              // Clear existing timeout
              if (batchTimeoutRef.current) {
                clearTimeout(batchTimeoutRef.current);
              }

              // Batch updates: apply after 50ms or immediately if batch is large
              batchTimeoutRef.current = window.setTimeout(() => {
                applyBatchedUpdates();
              }, 50);
            } else if (data.type === 'error') {
              setError(data.message || 'Unknown error');
            }
          } catch (err) {
            console.error('Error parsing watchlist message:', err);
          }
        };

        ws.onerror = (err) => {
          console.error('Watchlist WebSocket error:', err);
          setError('Connection error');
          setIsConnected(false);
        };

        ws.onclose = () => {
          setIsConnected(false);
          console.log('Watchlist WebSocket disconnected');
          
          // Attempt to reconnect after 3 seconds
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connectWebSocket();
          }, 3000);
        };
      } catch (err) {
        console.error('Failed to create WebSocket:', err);
        setError('Failed to connect');
        setIsConnected(false);
      }
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (batchTimeoutRef.current) {
        clearTimeout(batchTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Apply batched updates to prevent flickering
  const applyBatchedUpdates = () => {
    const batch = updateBatchRef.current;
    if (batch.size === 0) return;

    // Process stocks updates
    const stockUpdates = Array.from(batch.values()).filter(u => u.assetClass === 'stocks');
    if (stockUpdates.length > 0) {
      setStocks(prev => {
        const updated = [...prev];
        stockUpdates.forEach(update => {
          const index = updated.findIndex(s => s.symbol === update.symbol);
          if (index >= 0) {
            // Merge update with existing item to preserve all fields
            updated[index] = {
              ...updated[index], // Keep existing data
              price: update.price ?? updated[index].price,
              change: update.change ?? updated[index].change,
              changePercent: update.changePercent ?? updated[index].changePercent,
              volume: update.volume ?? updated[index].volume,
              lastUpdate: update.lastUpdate,
            };
          } else {
            // Symbol doesn't exist - add it (shouldn't happen normally)
            updated.push(update);
          }
        });
        return updated;
      });
    }

    // Process crypto updates
    const cryptoUpdates = Array.from(batch.values()).filter(u => u.assetClass === 'crypto');
    if (cryptoUpdates.length > 0) {
      setCrypto(prev => {
        const updated = [...prev];
        cryptoUpdates.forEach(update => {
          const index = updated.findIndex(s => s.symbol === update.symbol);
          if (index >= 0) {
            // Merge update with existing item to preserve all fields
            updated[index] = {
              ...updated[index], // Keep existing data
              price: update.price ?? updated[index].price,
              change: update.change ?? updated[index].change,
              changePercent: update.changePercent ?? updated[index].changePercent,
              volume: update.volume ?? updated[index].volume,
              lastUpdate: update.lastUpdate,
            };
          } else {
            // Symbol doesn't exist - add it (shouldn't happen normally)
            updated.push(update);
          }
        });
        return updated;
      });
    }

    // Clear batch
    batch.clear();
  };

  // Subscribe to symbols via WebSocket
  const subscribeToSymbols = useRef((ws: WebSocket, stocksList: WatchlistItem[], cryptoList: WatchlistItem[]) => {
    const allSymbols = [
      ...stocksList.map(s => ({ symbol: s.symbol, assetClass: 'stocks' })),
      ...cryptoList.map(s => ({ symbol: s.symbol, assetClass: 'crypto' })),
    ];
    ws.send(JSON.stringify({ type: 'subscribe', symbols: allSymbols }));
  });

  // Update subscription when symbols change
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      subscribeToSymbols.current(wsRef.current, stocksRef.current, cryptoRef.current);
    }
  }, [stocks, crypto]);

  // Add symbol function
  const handleAddSymbol = () => {
    const symbol = newSymbol.trim().toUpperCase();
    if (!symbol) return;

    // Auto-detect crypto symbols (end with USD/USDT) and suggest switching tabs
    const looksLikeCrypto = /^[A-Z]+(USD|USDT)$/.test(symbol);
    const looksLikeStock = /^[A-Z]{1,5}$/.test(symbol);

    // Validate symbol format based on active tab
    const assetClass = activeTab;
    if (assetClass === 'stocks') {
      if (looksLikeCrypto) {
        setError(`"${symbol}" looks like a crypto symbol. Switch to the Crypto tab to add it.`);
        return;
      }
      // Stock symbols are typically 1-5 uppercase letters
      if (!looksLikeStock) {
        setError('Invalid stock symbol format. Use 1-5 uppercase letters (e.g., AAPL)');
        return;
      }
    } else {
      // Crypto symbols typically end with USD or USDT
      if (!looksLikeCrypto) {
        if (looksLikeStock) {
          setError(`"${symbol}" looks like a stock symbol. Switch to the Stocks tab to add it.`);
        } else {
          setError('Invalid crypto symbol format. Use format like BTCUSD or ETHUSDT');
        }
        return;
      }
    }

    // Check if symbol already exists
    const currentItems = assetClass === 'stocks' ? stocks : crypto;
    if (currentItems.some(item => item.symbol === symbol)) {
      setError(`Symbol ${symbol} is already in the watchlist`);
      return;
    }

    // Add new symbol
    const newItem: WatchlistItem = {
      symbol,
      price: null,
      change: null,
      changePercent: null,
      volume: null,
      assetClass,
      lastUpdate: Date.now(),
    };

    if (assetClass === 'stocks') {
      setStocks(prev => [...prev, newItem]);
    } else {
      setCrypto(prev => [...prev, newItem]);
    }

    setNewSymbol('');
    setError(null);
  };

  // Remove symbol function
  const handleRemoveSymbol = (symbol: string, assetClass: 'stocks' | 'crypto') => {
    if (assetClass === 'stocks') {
      setStocks(prev => prev.filter(item => item.symbol !== symbol));
    } else {
      setCrypto(prev => prev.filter(item => item.symbol !== symbol));
    }
  };

  // Handle Enter key in input
  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleAddSymbol();
    }
  };

  const formatPrice = (price: number | null): string => {
    if (price === null) return '--';
    return price.toFixed(2);
  };

  const formatChange = (change: number | null): string => {
    if (change === null) return '--';
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}`;
  };

  const formatChangePercent = (changePercent: number | null): string => {
    if (changePercent === null) return '--';
    const sign = changePercent >= 0 ? '+' : '';
    return `${sign}${changePercent.toFixed(2)}%`;
  };

  const formatVolume = (volume: number | null): string => {
    if (volume === null) return '--';
    if (volume >= 1e9) return `${(volume / 1e9).toFixed(2)}B`;
    if (volume >= 1e6) return `${(volume / 1e6).toFixed(2)}M`;
    if (volume >= 1e3) return `${(volume / 1e3).toFixed(2)}K`;
    return volume.toFixed(0);
  };

  const getChangeColor = (change: number | null): string => {
    if (change === null) return '';
    return change >= 0 ? 'positive' : 'negative';
  };

  // Sort function
  const sortItems = (items: WatchlistItem[], column: SortColumn, direction: SortDirection): WatchlistItem[] => {
    if (!column) return items;

    const sorted = [...items].sort((a, b) => {
      let comparison = 0;

      switch (column) {
        case 'symbol':
          comparison = a.symbol.localeCompare(b.symbol);
          break;
        case 'price':
          const priceA = a.price ?? -Infinity;
          const priceB = b.price ?? -Infinity;
          comparison = priceA - priceB;
          break;
        case 'change':
          const changeA = a.change ?? -Infinity;
          const changeB = b.change ?? -Infinity;
          comparison = changeA - changeB;
          break;
        case 'changePercent':
          const changePercentA = a.changePercent ?? -Infinity;
          const changePercentB = b.changePercent ?? -Infinity;
          comparison = changePercentA - changePercentB;
          break;
        case 'volume':
          const volumeA = a.volume ?? -Infinity;
          const volumeB = b.volume ?? -Infinity;
          comparison = volumeA - volumeB;
          break;
      }

      return direction === 'asc' ? comparison : -comparison;
    });

    return sorted;
  };

  // Handle column header click
  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      // Toggle direction if clicking the same column
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new column and default to ascending
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const currentItems = activeTab === 'stocks' ? stocks : crypto;
  const sortedItems = sortItems(currentItems, sortColumn, sortDirection);

  // Calculate responsive spacing based on panel width
  useEffect(() => {
    const updateSpacing = () => {
      const panel = document.querySelector('.right-panel-container');
      if (!panel) return;
      
      const width = panel.clientWidth;
      // Calculate gap: scales from 0px at 420px to 12px at 1000px+
      // Very tight spacing to maximize middle canvas space
      const minGap = 0;
      const maxGap = 12;
      const minWidth = 420;
      const maxWidth = 1000;
      const gap = width <= minWidth 
        ? minGap 
        : minGap + Math.min(maxGap - minGap, ((width - minWidth) / (maxWidth - minWidth)) * (maxGap - minGap));
      
      // Calculate padding: smaller panel = smaller padding
      const minPadding = 4;
      const maxPadding = 12;
      const padding = Math.max(minPadding, Math.min(maxPadding, minPadding + ((width - minWidth) / (maxWidth - minWidth)) * (maxPadding - minPadding)));
      
      // Calculate right padding separately - keep it minimal to bring Volume closer to edge
      const minPaddingRight = 2;
      const maxPaddingRight = 6;
      const paddingRight = Math.max(minPaddingRight, Math.min(maxPaddingRight, minPaddingRight + ((width - minWidth) / (maxWidth - minWidth)) * (maxPaddingRight - minPaddingRight)));
      
      document.documentElement.style.setProperty('--watchlist-column-gap', `${gap}px`);
      document.documentElement.style.setProperty('--watchlist-row-padding', `${padding}px`);
      document.documentElement.style.setProperty('--watchlist-row-padding-right', `${paddingRight}px`);
    };

    updateSpacing();
    const resizeObserver = new ResizeObserver(updateSpacing);
    const panel = document.querySelector('.right-panel-container');
    if (panel) {
      resizeObserver.observe(panel);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <aside className="watchlist-panel">
      <div className="panel-header">
        <div className="panel-header-top">
          <h3 className="panel-title">Watchlist</h3>
          <div className="connection-status">
            <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`} />
            <span className="status-text">{isConnected ? 'Live' : 'Connecting...'}</span>
          </div>
        </div>
        <div className="watchlist-tabs">
          <button
            className={`tab-button ${activeTab === 'stocks' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('stocks');
              setSortColumn(null);
              setSortDirection('asc');
            }}
          >
            Stocks
          </button>
          <button
            className={`tab-button ${activeTab === 'crypto' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('crypto');
              setSortColumn(null);
              setSortDirection('asc');
            }}
          >
            Crypto
          </button>
        </div>
      </div>

      <div className="panel-content">
        {/* Add Symbol Input */}
        <div className="add-symbol-section">
          <div className="add-symbol-input-group">
            <input
              type="text"
              className="symbol-input"
              placeholder={
                activeTab === 'stocks' 
                  ? 'Add stock symbol (e.g., AAPL, MSFT)' 
                  : 'Add crypto symbol (e.g., BTCUSD, ETHUSD)'
              }
              value={newSymbol}
              onChange={(e) => {
                setNewSymbol(e.target.value.toUpperCase());
                setError(null);
              }}
              onKeyPress={handleKeyPress}
            />
            <button
              className="add-symbol-button"
              onClick={handleAddSymbol}
              disabled={!newSymbol.trim()}
              title="Add symbol"
            >
              +
            </button>
          </div>
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {!isConnected && !error && (
          <div className="empty-state">
            <p>Connecting to market data...</p>
          </div>
        )}

        {isConnected && (
          <>
            {currentItems.length === 0 ? (
              <div className="empty-state">
                <p>No symbols in watchlist</p>
                <small>Add symbols using the input above</small>
              </div>
            ) : (
              <div 
                className="watchlist-table-wrapper"
                onWheel={(e) => {
                  // Stop propagation to prevent canvas scrolling
                  e.stopPropagation();
                  // Allow native scrolling within the watchlist
                }}
              >
                <div className="watchlist-table">
                  <div className="table-header">
                    <div 
                      className={`col-symbol sortable ${sortColumn === 'symbol' ? 'sorted' : ''}`}
                      onClick={() => handleSort('symbol')}
                    >
                      Symbol
                      {sortColumn === 'symbol' && (
                        <span className="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </div>
                    <div 
                      className={`col-price sortable ${sortColumn === 'price' ? 'sorted' : ''}`}
                      onClick={() => handleSort('price')}
                    >
                      Price
                      {sortColumn === 'price' && (
                        <span className="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </div>
                    <div 
                      className={`col-change sortable ${sortColumn === 'change' ? 'sorted' : ''}`}
                      onClick={() => handleSort('change')}
                    >
                      Change
                      {sortColumn === 'change' && (
                        <span className="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </div>
                    <div 
                      className={`col-change-pct sortable ${sortColumn === 'changePercent' ? 'sorted' : ''}`}
                      onClick={() => handleSort('changePercent')}
                    >
                      %
                      {sortColumn === 'changePercent' && (
                        <span className="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </div>
                    <div 
                      className={`col-volume sortable ${sortColumn === 'volume' ? 'sorted' : ''}`}
                      onClick={() => handleSort('volume')}
                    >
                      Volume
                      {sortColumn === 'volume' && (
                        <span className="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </div>
                    <div className="col-actions"></div>
                  </div>
                  <div 
                    ref={tableBodyRef}
                    className="table-body"
                    tabIndex={-1}
                  >
                    {sortedItems.map((item) => (
                    <div key={item.symbol} className="table-row">
                      <div className="col-symbol">{item.symbol}</div>
                      <div className="col-price">{formatPrice(item.price)}</div>
                      <div className={`col-change ${getChangeColor(item.change)}`}>
                        {formatChange(item.change)}
                      </div>
                      <div className={`col-change-pct ${getChangeColor(item.changePercent)}`}>
                        {formatChangePercent(item.changePercent)}
                      </div>
                      <div className="col-volume">{formatVolume(item.volume)}</div>
                      <div className="col-actions">
                        <button
                          className="remove-symbol-button"
                          onClick={() => handleRemoveSymbol(item.symbol, item.assetClass)}
                          title="Remove symbol"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

