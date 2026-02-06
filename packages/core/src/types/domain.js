// src/types/domain.ts
// Domain types: enums, core value types, and type aliases
// ============ Enums ============
export var AssetClass;
(function (AssetClass) {
    AssetClass["CRYPTO"] = "CRYPTO";
    AssetClass["STOCKS"] = "STOCKS";
})(AssetClass || (AssetClass = {}));
export var InstrumentType;
(function (InstrumentType) {
    InstrumentType["SPOT"] = "SPOT";
    InstrumentType["PERPETUAL"] = "PERPETUAL";
    InstrumentType["FUTURE"] = "FUTURE";
    InstrumentType["OPTION"] = "OPTION";
})(InstrumentType || (InstrumentType = {}));
export var Provider;
(function (Provider) {
    Provider["BINANCE"] = "BINANCE";
    Provider["POLYGON"] = "POLYGON";
})(Provider || (Provider = {}));
export var IndicatorType;
(function (IndicatorType) {
    IndicatorType["EMA"] = "EMA";
    IndicatorType["SMA"] = "SMA";
    IndicatorType["MACD"] = "MACD";
    IndicatorType["RSI"] = "RSI";
    IndicatorType["ADX"] = "ADX";
    IndicatorType["HURST"] = "HURST";
    IndicatorType["BOLLINGER"] = "BOLLINGER";
    IndicatorType["VOLUME_RATIO"] = "VOLUME_RATIO";
    IndicatorType["EIS"] = "EIS";
    IndicatorType["ATRX"] = "ATRX";
    IndicatorType["ATR"] = "ATR";
    IndicatorType["EMA_RANGE"] = "EMA_RANGE";
    IndicatorType["ORB"] = "ORB";
    IndicatorType["LOD"] = "LOD";
    IndicatorType["VBP"] = "VBP";
    IndicatorType["EVWMA"] = "EVWMA";
    IndicatorType["CCO"] = "CCO";
})(IndicatorType || (IndicatorType = {}));
export var ProgressState;
(function (ProgressState) {
    ProgressState["START"] = "start";
    ProgressState["UPDATE"] = "update";
    ProgressState["DONE"] = "done";
    ProgressState["ERROR"] = "error";
    ProgressState["STOPPED"] = "stopped";
})(ProgressState || (ProgressState = {}));
export var ExecutionOutcome;
(function (ExecutionOutcome) {
    ExecutionOutcome["SUCCESS"] = "success";
    ExecutionOutcome["CANCELLED"] = "cancelled";
    ExecutionOutcome["ERROR"] = "error";
})(ExecutionOutcome || (ExecutionOutcome = {}));
export var NodeCategory;
(function (NodeCategory) {
    NodeCategory["IO"] = "io";
    NodeCategory["LLM"] = "llm";
    NodeCategory["MARKET"] = "market";
    NodeCategory["BASE"] = "base";
    NodeCategory["CORE"] = "core";
})(NodeCategory || (NodeCategory = {}));
export class AssetSymbol {
    ticker;
    assetClass;
    quoteCurrency;
    instrumentType;
    metadata;
    constructor(ticker, assetClass, quoteCurrency, instrumentType = InstrumentType.SPOT, metadata = {}) {
        this.ticker = ticker;
        this.assetClass = assetClass;
        this.quoteCurrency = quoteCurrency;
        this.instrumentType = instrumentType;
        this.metadata = metadata;
    }
    toString() {
        if (this.assetClass === AssetClass.CRYPTO && this.quoteCurrency) {
            return `${this.ticker.toUpperCase()}${this.quoteCurrency.toUpperCase()}`;
        }
        return this.ticker.toUpperCase();
    }
    static fromString(s, assetClass, metadata = {}) {
        if (assetClass === AssetClass.CRYPTO) {
            if (s.toUpperCase().includes('USDT')) {
                const ticker = s.toUpperCase().split('USDT')[0] ?? s.toUpperCase();
                return new AssetSymbol(ticker, assetClass, 'USDT', InstrumentType.SPOT, metadata);
            }
            return new AssetSymbol(s.toUpperCase(), assetClass, undefined, InstrumentType.SPOT, metadata);
        }
        return new AssetSymbol(s.toUpperCase(), assetClass, undefined, InstrumentType.SPOT, metadata);
    }
    toDict() {
        return {
            ticker: this.ticker,
            asset_class: this.assetClass,
            quote_currency: this.quoteCurrency,
            instrument_type: this.instrumentType,
            metadata: this.metadata,
        };
    }
    // For use as Map key - generates unique string identifier
    get key() {
        return `${this.ticker}:${this.assetClass}:${this.quoteCurrency ?? ''}:${this.instrumentType}`;
    }
}
export function createIndicatorValue(options = {}) {
    return {
        single: options.single ?? 0.0,
        lines: options.lines ?? {},
        series: options.series ?? [],
    };
}
export function createIndicatorResult(options) {
    return {
        indicatorType: options.indicatorType,
        timestamp: options.timestamp ?? null,
        values: options.values ?? createIndicatorValue(),
        params: options.params ?? {},
        error: options.error ?? null,
    };
}
