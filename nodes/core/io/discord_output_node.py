import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class DiscordOutput(Base):
    """
    Node to post OHLCV data summaries to a Discord channel via webhook.

    Inputs:
    - ohlcv_bundle: OHLCVBundle - The OHLCV data to summarize
    - execution_summary: str (optional) - Optional graph execution summary

    Parameters:
    - include_summary: bool - Whether to include execution summary if provided
    - max_symbols: int - Maximum number of symbols to include in the message
    - color_success: str - Hex color for embed (default: green)
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
        "execution_summary": str,
    }
    outputs = {}  # No outputs - this is a sink node

    CATEGORY = NodeCategory.IO
    required_keys = ["DISCORD_WEBHOOK_URL"]

    default_params = {
        "include_summary": True,
        "max_symbols": 10,
        "color_success": "0x00ff00",
    }

    params_meta = [
        {"name": "include_summary", "type": "combo", "default": True, "options": [True, False]},
        {"name": "max_symbols", "type": "number", "default": 10, "min": 1, "max": 50, "step": 1},
        {"name": "color_success", "type": "text", "default": "0x00ff00"},
    ]

    def __init__(self, id: int, params: dict[str, Any]):
        super().__init__(id, params)
        self.optional_inputs = ["execution_summary"]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ohlcv_bundle = inputs.get("ohlcv_bundle", {})
        execution_summary = inputs.get("execution_summary", "")

        if not ohlcv_bundle:
            logger.warning(f"DiscordOutput node {self.id}: No OHLCV bundle provided")
            return {}

        # Get webhook URL from vault
        vault = APIKeyVault()
        webhook_url = vault.get("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL not found in API key vault")

        # Format the embeds
        embeds = self._format_ohlcv_embeds(ohlcv_bundle)

        # Add execution summary if provided
        if execution_summary and self.params.get("include_summary", True):
            summary_embed: dict[str, Any] = {
                "title": "📊 Execution Summary",
                "description": execution_summary,
                "color": 0x3498DB,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            embeds.insert(0, summary_embed)

        # Post to Discord
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json={"embeds": embeds},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    logger.info(f"DiscordOutput node {self.id}: Successfully posted to Discord")
                    return {}
        except aiohttp.ClientError as e:
            logger.error(f"DiscordOutput node {self.id}: HTTP error posting to Discord: {e}")
            raise
        except Exception as e:
            logger.error(f"DiscordOutput node {self.id}: Unexpected error: {e}")
            raise

    def _format_ohlcv_embeds(
        self, bundle: dict[AssetSymbol, list[OHLCVBar]]
    ) -> list[dict[str, Any]]:
        """Format OHLCV bundle data into Discord embeds."""
        embeds: list[dict[str, Any]] = []
        max_symbols_param = self.params.get("max_symbols", 10)
        max_symbols = (
            int(max_symbols_param) if isinstance(max_symbols_param, (int, float, str)) else 10
        )
        color_str = str(self.params.get("color_success", "0x00ff00"))
        color = int(color_str, 16)

        for symbol, bars in list(bundle.items())[:max_symbols]:
            if not bars:
                continue

            latest = bars[-1]
            summary = self._calculate_summary(bars)

            # Build fields
            fields: list[dict[str, Any]] = [
                {"name": "💰 Current Price", "value": f"${latest['close']:.2f}", "inline": True},
                {"name": "📈 High", "value": f"${latest['high']:.2f}", "inline": True},
                {"name": "📉 Low", "value": f"${latest['low']:.2f}", "inline": True},
                {"name": "📊 Volume", "value": f"{latest['volume']:,.0f}", "inline": True},
                {"name": "🔢 Bars", "value": str(len(bars)), "inline": True},
            ]

            # Add price change if multiple bars
            if len(bars) > 1:
                change = latest["close"] - bars[0]["open"]
                change_pct = (change / bars[0]["open"]) * 100
                change_emoji = "📈" if change >= 0 else "📉"
                fields.append(
                    {
                        "name": f"{change_emoji} Change",
                        "value": f"{change:+.2f} ({change_pct:+.2f}%)",
                        "inline": True,
                    }
                )

            # Add summary stats
            fields.extend(
                [
                    {
                        "name": "📊 Avg Price",
                        "value": f"${summary['avg_price']:.2f}",
                        "inline": True,
                    },
                    {"name": "📈 Range High", "value": f"${summary['high']:.2f}", "inline": True},
                    {"name": "📉 Range Low", "value": f"${summary['low']:.2f}", "inline": True},
                ]
            )

            embed: dict[str, Any] = {
                "title": f"📊 {symbol}",
                "color": color,
                "fields": fields,
                "timestamp": datetime.fromtimestamp(latest["timestamp"] / 1000).isoformat(),
            }

            embeds.append(embed)

        return embeds

    def _calculate_summary(self, bars: list[OHLCVBar]) -> dict[str, float]:
        """Calculate summary statistics for OHLCV bars."""
        if not bars:
            return {"avg_price": 0.0, "total_volume": 0.0, "high": 0.0, "low": 0.0}

        prices = [b["close"] for b in bars]
        volumes = [b["volume"] for b in bars]

        return {
            "avg_price": sum(prices) / len(prices),
            "total_volume": sum(volumes),
            "high": max(b["high"] for b in bars),
            "low": min(b["low"] for b in bars),
        }
