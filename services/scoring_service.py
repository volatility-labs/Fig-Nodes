import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class ScoringService:
    def __init__(self, indicators_service, warmup_passes: int = 3, warmup_window_min: int = 15):
        self.indicators_service = indicators_service
        self.warmup_passes = warmup_passes
        self.warmup_window = timedelta(minutes=warmup_window_min)
        self._score_cache: Dict[str, Dict[str, Any]] = {}
        self.SCORING_WEIGHTS = {
            "hurst": 0.15,
            "acceleration": 0.15,
            "adx": 0.05,
            "volume_ratio": 0.10,
            "res_pct": 0.20,
            "sup_pct": -0.10,  # Negative weight for downside
            "risk_reward": 0.25
        }

    def update_score(self, symbol: str, timeframe: str, df: pd.DataFrame):
        indicators = self.indicators_service.compute_indicators(df, timeframe)
        if not indicators:
            return
        logger.info(f"Indicators for {symbol} on {timeframe}: {indicators}")
        score = self.compute_score(indicators)
        now = datetime.now(timezone.utc)
        cache_entry = self._score_cache.setdefault(symbol, {'scores': [], 'last_update': now})
        cache_entry['scores'].append({'score': score, 'timestamp': now, 'passes': score > 70})  # Example threshold
        cache_entry['last_update'] = now
        logger.info(f'Updated score for {symbol} on {timeframe}: {score}')

    def compute_score(self, indicators: Dict) -> float:
        if not indicators:
            return 0.0
        
        # Calculate risk-reward
        rr = indicators.get('res_pct', 0) / indicators.get('sup_pct', 1) if indicators.get('sup_pct', 0) > 0 else 0
        
        # Gather weighted components
        components = {
            "hurst": indicators.get('hurst', 0.5),
            "acceleration": indicators.get('acceleration', 0),
            "adx": indicators.get('adx', 0),
            "volume_ratio": indicators.get('volume_ratio', 1),
            "res_pct": indicators.get('res_pct', 0),
            "sup_pct": indicators.get('sup_pct', 0),
            "risk_reward": rr
        }
        
        score = 0.0
        calc_log = []
        for key, value in components.items():
            weighted = self.SCORING_WEIGHTS.get(key, 0) * value
            score += weighted
            calc_log.append(f"{key}: {value} * {self.SCORING_WEIGHTS.get(key, 0)} = {weighted}")
        
        logger.info(f"Score calculation: {'; '.join(calc_log)}; Total: {score}")
        return score

    def is_warmed_up(self, symbol: str) -> bool:
        if symbol not in self._score_cache:
            return False
        now = datetime.now(timezone.utc)
        recent_passes = [s for s in self._score_cache[symbol]['scores'] if now - s['timestamp'] < self.warmup_window and s['passes']]
        return len(recent_passes) >= self.warmup_passes

    def get_top_tradable(self, n: int = 4) -> List[Dict]:
        tradable = [s for s in self._score_cache if self.is_warmed_up(s)]
        sorted_tradable = sorted(tradable, key=lambda x: self._score_cache[x]['scores'][-1]['score'], reverse=True)
        return [{ 'symbol': s, 'score': self._score_cache[s]['scores'][-1]['score'] } for s in sorted_tradable[:n]] 