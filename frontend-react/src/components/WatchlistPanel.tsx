import { useState, useEffect, useRef } from 'react';
import './WatchlistPanel.css';

// TickerLogo component - handles stocks and crypto separately
function TickerLogo({ tickerDetails }: { tickerDetails: TickerDetails }) {
  const [showPlaceholder, setShowPlaceholder] = useState(false);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

  useEffect(() => {
    setShowPlaceholder(false);
    setLogoUrl(null);
    
    const isCrypto = tickerDetails.assetClass === 'crypto';
    
    if (isCrypto) {
      // For crypto: Use Google favicon from known crypto websites
      const cryptoWebsiteMap: Record<string, string> = {
        'BTC': 'bitcoin.org',
        'ETH': 'ethereum.org',
        'SOL': 'solana.com',
        'ADA': 'cardano.org',
        'DOT': 'polkadot.network',
        'LTC': 'litecoin.org',
        'MATIC': 'polygon.technology',
        'AVAX': 'avax.network',
        'XRP': 'ripple.com',
        'DOGE': 'dogecoin.com',
        'BNB': 'binance.com',
      };
      
      // Extract base symbol (e.g., "X:BTCUSD" or "BTCUSD" -> "BTC")
      const baseSymbol = tickerDetails.ticker.replace('USD', '').replace('X:', '').toUpperCase();
      const cryptoDomain = cryptoWebsiteMap[baseSymbol];
      
      if (cryptoDomain) {
        setLogoUrl(`https://www.google.com/s2/favicons?domain=${cryptoDomain}&sz=128`);
        return;
      }
      
      // Fallback: try homepage_url if available
      if (tickerDetails.homepage_url) {
        try {
          const domain = new URL(tickerDetails.homepage_url).hostname;
          setLogoUrl(`https://www.google.com/s2/favicons?domain=${domain}&sz=128`);
          return;
        } catch (e) {
          // Invalid URL
        }
      }
    } else {
      // For stocks: Use Google favicon from homepage_url (Polygon logos don't work reliably)
      if (tickerDetails.homepage_url) {
        try {
          const domain = new URL(tickerDetails.homepage_url).hostname;
          setLogoUrl(`https://www.google.com/s2/favicons?domain=${domain}&sz=128`);
          return;
        } catch (e) {
          // Invalid URL
        }
      }
    }
    
    // No logo found - show placeholder
    setShowPlaceholder(true);
  }, [tickerDetails.ticker, tickerDetails.homepage_url, tickerDetails.logo_url, tickerDetails.assetClass]);

  if (showPlaceholder || !logoUrl) {
    return (
      <div className="ticker-logo-container">
        <div className="ticker-logo-placeholder">
          {tickerDetails.ticker?.charAt(0) || '?'}
        </div>
      </div>
    );
  }

  return (
    <div className="ticker-logo-container">
      <img 
        src={logoUrl}
        alt={tickerDetails.name || tickerDetails.ticker || 'Logo'}
        className="ticker-logo"
        onError={() => setShowPlaceholder(true)}
      />
    </div>
  );
}

interface WatchlistItem {
  symbol: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  volume: number | null;
  assetClass: 'stocks' | 'crypto';
  lastUpdate: number;
}

interface TickerDetails {
  ticker: string;
  name: string;
  description?: string;
  homepage_url?: string;
  logo_url?: string;
  icon_url?: string;
  market_cap?: number;
  total_employees?: number;
  phone_number?: string;
  address?: {
    address1?: string;
    city?: string;
    state?: string;
    postal_code?: string;
  };
  sic_description?: string;
  list_date?: string;
  locale?: string;
  market?: string;
  primary_exchange?: string;
  type?: string;
  currency_name?: string;
  active?: boolean;
  assetClass?: 'stocks' | 'crypto'; // Added for UI logic
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
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [tickerDetails, setTickerDetails] = useState<TickerDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
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
          console.log('WatchlistPanel: Current symbols in refs:', {
            stocks: stocksRef.current.map(s => s.symbol),
            crypto: cryptoRef.current.map(s => s.symbol)
          });
          
          // Send subscription with current symbols from refs
          subscribeToSymbols.current(ws, stocksRef.current, cryptoRef.current);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('WatchlistPanel: Received WebSocket message:', data);
            
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
              console.error('WatchlistPanel: WebSocket error:', data.message);
              setError(data.message || 'Unknown error');
            }
          } catch (err) {
            console.error('Error parsing watchlist message:', err, event.data);
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
    console.log('WatchlistPanel: Subscribing to symbols:', allSymbols);
    ws.send(JSON.stringify({ type: 'subscribe', symbols: allSymbols }));
  });

  // Update subscription when symbols change
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      subscribeToSymbols.current(wsRef.current, stocksRef.current, cryptoRef.current);
    }
  }, [stocks, crypto]);

  // Listen for Logging node symbols to auto-add to watchlist
  useEffect(() => {
    const handleLoggingNodeSymbols = (event: CustomEvent<{ symbols: string[]; nodeId: number }>) => {
      const { symbols } = event.detail;
      if (!symbols || symbols.length === 0) return;

      console.log('WatchlistPanel: Received symbols from Logging node:', symbols);

      // Add symbols to stocks watchlist (assuming they're stock symbols)
      // Users can manually move them to crypto if needed
      const newSymbols: WatchlistItem[] = [];
      const existingSymbols = new Set(stocks.map(s => s.symbol));

      symbols.forEach(symbol => {
        const upperSymbol = symbol.trim().toUpperCase();
        if (!upperSymbol) return;

        // Skip if already in watchlist
        if (existingSymbols.has(upperSymbol)) {
          console.log(`Symbol ${upperSymbol} already in watchlist, skipping`);
          return;
        }

        // Validate symbol format (stock symbols are typically 1-5 uppercase letters)
        const looksLikeStock = /^[A-Z]{1,5}$/.test(upperSymbol);
        if (!looksLikeStock) {
          console.log(`Symbol ${upperSymbol} doesn't look like a stock symbol, skipping`);
          return;
        }

        newSymbols.push({
          symbol: upperSymbol,
          price: null,
          change: null,
          changePercent: null,
          volume: null,
          assetClass: 'stocks',
          lastUpdate: Date.now(),
        });
      });

      if (newSymbols.length > 0) {
        console.log(`WatchlistPanel: Adding ${newSymbols.length} symbol(s) to watchlist:`, newSymbols.map(s => s.symbol));
        setStocks(prev => {
          const updated = [...prev, ...newSymbols];
          // Update ref immediately for subscription
          stocksRef.current = updated;
          
          // Subscribe to new symbols immediately if WebSocket is open
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            subscribeToSymbols.current(wsRef.current, updated, cryptoRef.current);
          }
          
          return updated;
        });
        // Clear any error messages
        setError(null);
      }
    };

    window.addEventListener('loggingNodeSymbols', handleLoggingNodeSymbols as EventListener);
    
    return () => {
      window.removeEventListener('loggingNodeSymbols', handleLoggingNodeSymbols as EventListener);
    };
  }, [stocks]);

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

  // Fetch ticker details
  const fetchTickerDetails = async (ticker: string, assetClass: 'stocks' | 'crypto') => {
    setLoadingDetails(true);
    setSelectedTicker(ticker);
    
    try {
      // For crypto, Polygon ticker details endpoint expects format WITHOUT "X:" prefix
      // e.g., "BTCUSD" not "X:BTCUSD"
      let apiTicker = ticker;
      if (assetClass === 'crypto' && ticker.startsWith('X:')) {
        apiTicker = ticker.replace('X:', '');
      }
      
      const response = await fetch(`http://localhost:8000/api/v1/watchlist/ticker/${encodeURIComponent(apiTicker)}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch ticker details');
      }
      
      const data = await response.json();
      
      if (data.error) {
        console.error('Error fetching ticker details:', data.error);
        setTickerDetails(null);
      } else {
        // Debug: log what we received
        console.log('WatchlistPanel: Received ticker details:', data);
        // Add asset class to details for UI logic
        setTickerDetails({ ...data, assetClass });
      }
    } catch (error) {
      console.error('Error fetching ticker details:', error);
      setTickerDetails(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  // Handle ticker row click
  const handleTickerClick = (ticker: string, assetClass: 'stocks' | 'crypto') => {
    if (selectedTicker === ticker) {
      // Click same ticker - collapse details
      setSelectedTicker(null);
      setTickerDetails(null);
    } else {
      // Click different ticker - fetch and show details
      fetchTickerDetails(ticker, assetClass);
    }
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
          {currentItems.length > 0 && (
            <button
              className="clear-watchlist-button"
              onClick={() => {
                if (activeTab === 'stocks') {
                  setStocks([]);
                  stocksRef.current = [];
                  // Update WebSocket subscription immediately
                  if (wsRef.current?.readyState === WebSocket.OPEN) {
                    subscribeToSymbols.current(wsRef.current, [], cryptoRef.current);
                  }
                } else {
                  setCrypto([]);
                  cryptoRef.current = [];
                  // Update WebSocket subscription immediately
                  if (wsRef.current?.readyState === WebSocket.OPEN) {
                    subscribeToSymbols.current(wsRef.current, stocksRef.current, []);
                  }
                }
                setError(null);
              }}
              title={`Clear all ${activeTab} symbols`}
            >
              🗑️ Clear Watchlist
            </button>
          )}
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
                    <div 
                      key={item.symbol} 
                      className={`table-row ${selectedTicker === item.symbol ? 'selected' : ''} clickable`}
                      onClick={() => {
                        // Allow details for both stocks and crypto
                        handleTickerClick(item.symbol, item.assetClass);
                      }}
                    >
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
                          onClick={(e) => {
                            e.stopPropagation(); // Prevent row click
                            handleRemoveSymbol(item.symbol, item.assetClass);
                          }}
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

        {/* Ticker Details Panel */}
        {selectedTicker && (
          <div className="ticker-details-panel">
            {loadingDetails ? (
              <div className="details-loading">Loading details...</div>
            ) : tickerDetails ? (
              <>
                <div className="details-header">
                  <div className="details-title-row">
                    <TickerLogo tickerDetails={tickerDetails} />
                    <div className="details-title-info">
                      <h4 className="ticker-name">{tickerDetails.name}</h4>
                      <div className="ticker-meta">
                        <span className="ticker-symbol">{tickerDetails.ticker}</span>
                        {tickerDetails.primary_exchange && (
                          <span className="ticker-exchange">• {tickerDetails.primary_exchange}</span>
                        )}
                        {tickerDetails.type && (
                          <span className="ticker-type">• {tickerDetails.type}</span>
                        )}
                      </div>
                    </div>
                    <button 
                      className="close-details-button"
                      onClick={() => {
                        setSelectedTicker(null);
                        setTickerDetails(null);
                      }}
                      title="Close details"
                    >
                      ×
                    </button>
                  </div>
                </div>
                
                <div className="details-body">
                  {tickerDetails.description && (
                    <div className="details-section">
                      <p className="ticker-description">{tickerDetails.description}</p>
                    </div>
                  )}
                  
                  {!tickerDetails.description && tickerDetails.assetClass === 'crypto' && (
                    <div className="details-section">
                      <p className="ticker-description" style={{ color: 'var(--theme-text-secondary)', fontStyle: 'italic' }}>
                        No description available. Click the links below for more information.
                      </p>
                    </div>
                  )}
                  
                  <div className="details-grid">
                    {tickerDetails.market_cap && (
                      <div className="detail-item">
                        <span className="detail-label">Market Cap</span>
                        <span className="detail-value">
                          {tickerDetails.market_cap >= 1e12 
                            ? `$${(tickerDetails.market_cap / 1e12).toFixed(2)}T`
                            : tickerDetails.market_cap >= 1e9
                            ? `$${(tickerDetails.market_cap / 1e9).toFixed(2)}B`
                            : `$${(tickerDetails.market_cap / 1e6).toFixed(2)}M`}
                        </span>
                      </div>
                    )}
                    
                    {tickerDetails.market && (
                      <div className="detail-item">
                        <span className="detail-label">Market</span>
                        <span className="detail-value">{tickerDetails.market.toUpperCase()}</span>
                      </div>
                    )}
                    
                    {tickerDetails.type && (
                      <div className="detail-item">
                        <span className="detail-label">Type</span>
                        <span className="detail-value">{tickerDetails.type}</span>
                      </div>
                    )}
                    
                    {tickerDetails.total_employees && tickerDetails.assetClass !== 'crypto' && (
                      <div className="detail-item">
                        <span className="detail-label">Employees</span>
                        <span className="detail-value">
                          {tickerDetails.total_employees.toLocaleString()}
                        </span>
                      </div>
                    )}
                    
                    {tickerDetails.sic_description && tickerDetails.assetClass !== 'crypto' && (
                      <div className="detail-item">
                        <span className="detail-label">Industry</span>
                        <span className="detail-value">{tickerDetails.sic_description}</span>
                      </div>
                    )}
                    
                    {tickerDetails.list_date && (
                      <div className="detail-item">
                        <span className="detail-label">{tickerDetails.assetClass === 'crypto' ? 'Launched' : 'Listed'}</span>
                        <span className="detail-value">{tickerDetails.list_date}</span>
                      </div>
                    )}
                    
                    {tickerDetails.currency_name && tickerDetails.assetClass === 'crypto' && (
                      <div className="detail-item">
                        <span className="detail-label">Currency</span>
                        <span className="detail-value">{tickerDetails.currency_name}</span>
                      </div>
                    )}
                    
                    {tickerDetails.primary_exchange && (
                      <div className="detail-item">
                        <span className="detail-label">Exchange</span>
                        <span className="detail-value">{tickerDetails.primary_exchange}</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="details-section">
                    {tickerDetails.homepage_url && (
                      <a 
                        href={tickerDetails.homepage_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ticker-website-link"
                      >
                        🌐 Visit Website →
                      </a>
                    )}
                    
                    {/* OTC Markets link for OTC stocks */}
                    {tickerDetails.ticker && 
                     tickerDetails.assetClass === 'stocks' &&
                     (tickerDetails.market === 'otc' || 
                      tickerDetails.primary_exchange?.toUpperCase().includes('OTC')) && (
                        <a 
                          href={`https://www.otcmarkets.com/stock/${tickerDetails.ticker}/overview`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ticker-website-link otc-markets-link"
                        >
                          📊 View on OTC Markets →
                        </a>
                      )
                    }
                    
                    {/* Crypto links to CoinMarketCap and CoinGecko */}
                    {tickerDetails.ticker && tickerDetails.assetClass === 'crypto' && (() => {
                      // Extract base symbol (e.g., "X:LTCUSD" or "LTCUSD" -> "LTC")
                      const baseSymbol = tickerDetails.ticker.replace('USD', '').replace('X:', '').toUpperCase();
                      
                      // Map common crypto symbols to CoinMarketCap/CoinGecko slugs
                      const cryptoSlugMap: Record<string, { cmc: string; gecko: string }> = {
                        'BTC': { cmc: 'bitcoin', gecko: 'bitcoin' },
                        'ETH': { cmc: 'ethereum', gecko: 'ethereum' },
                        'SOL': { cmc: 'solana', gecko: 'solana' },
                        'ADA': { cmc: 'cardano', gecko: 'cardano' },
                        'DOT': { cmc: 'polkadot', gecko: 'polkadot-new' },
                        'LTC': { cmc: 'litecoin', gecko: 'litecoin' },
                        'MATIC': { cmc: 'polygon', gecko: 'matic-network' },
                        'AVAX': { cmc: 'avalanche', gecko: 'avalanche-2' },
                        'XRP': { cmc: 'xrp', gecko: 'ripple' },
                        'DOGE': { cmc: 'dogecoin', gecko: 'dogecoin' },
                        'BNB': { cmc: 'bnb', gecko: 'binancecoin' },
                        'USDT': { cmc: 'tether', gecko: 'tether' },
                        'USDC': { cmc: 'usd-coin', gecko: 'usd-coin' },
                      };
                      
                      const slugInfo = cryptoSlugMap[baseSymbol];
                      
                      if (slugInfo) {
                        return (
                          <>
                            <a 
                              href={`https://coinmarketcap.com/currencies/${slugInfo.cmc}/`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ticker-website-link crypto-link"
                            >
                              💰 View on CoinMarketCap →
                            </a>
                            <a 
                              href={`https://www.coingecko.com/en/coins/${slugInfo.gecko}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ticker-website-link crypto-link"
                            >
                              🦎 View on CoinGecko →
                            </a>
                          </>
                        );
                      } else {
                        // Fallback: link to search pages if we don't have a mapping
                        return (
                          <>
                            <a 
                              href={`https://coinmarketcap.com/currencies/?q=${baseSymbol}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ticker-website-link crypto-link"
                            >
                              💰 Search on CoinMarketCap →
                            </a>
                            <a 
                              href={`https://www.coingecko.com/en/search?query=${baseSymbol}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ticker-website-link crypto-link"
                            >
                              🦎 Search on CoinGecko →
                            </a>
                          </>
                        );
                      }
                    })()}
                  </div>
                  
                  {tickerDetails.address && tickerDetails.assetClass !== 'crypto' && (
                    <div className="details-section">
                      <div className="detail-label">Address</div>
                      <div className="ticker-address">
                        {tickerDetails.address.address1 && <div>{tickerDetails.address.address1}</div>}
                        {(tickerDetails.address.city || tickerDetails.address.state) && (
                          <div>
                            {tickerDetails.address.city}
                            {tickerDetails.address.city && tickerDetails.address.state && ', '}
                            {tickerDetails.address.state} {tickerDetails.address.postal_code}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="details-error">
                No details available for {selectedTicker}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}

