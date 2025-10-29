import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class DiscordOutput(Base):
    """
    Sends a list of symbols to Discord via webhook.
    
    Input:
    - symbols: List[AssetSymbol] - The symbols to send to Discord
    
    Output:
    - status: str - Success or error message
    
    Parameters:
    - message_template: str - Template for the Discord message
    - max_symbols_display: int - Maximum symbols to show (default: 50)
    """

    inputs = {"symbols": get_type("AssetSymbolList")}
    outputs = {"status": str}
    required_keys = []  # Optional key

    default_params = {
        "message_template": "📊 **Trading Symbols Update**\n\n{symbol_list}\n\n*Total: {count} symbols*",
        "max_symbols_display": 50,
    }

    params_meta = [
        {
            "name": "message_template",
            "type": "text",
            "default": "📊 **Trading Symbols Update**\n\n{symbol_list}\n\n*Total: {count} symbols*",
            "label": "Message Template",
            "description": "Discord message template. Use {symbol_list} and {count} placeholders.",
        },
        {
            "name": "max_symbols_display",
            "type": "integer",
            "default": 50,
            "label": "Max Symbols to Display",
            "description": "Maximum number of symbols to display in Discord (default: 50)",
        },
    ]

    CATEGORY = "io"
    uiModule = "DiscordOutputNodeUI"

    def _format_symbol_list(self, symbols: list[AssetSymbol], max_display: int) -> str:
        """Format symbols for Discord display."""
        if not symbols:
            return "*(No symbols)*"

        # Group symbols by asset class
        grouped: dict[str, list[str]] = {}
        for symbol in symbols:
            asset_class = symbol.asset_class.value if hasattr(symbol.asset_class, 'value') else str(symbol.asset_class)
            if asset_class not in grouped:
                grouped[asset_class] = []
            grouped[asset_class].append(symbol.ticker)

        # Build formatted string
        formatted_parts = []
        total_shown = 0
        
        for asset_class, tickers in grouped.items():
            tickers_to_show = min(len(tickers), max_display - total_shown)
            if tickers_to_show <= 0:
                break
            
            # Sort tickers alphabetically
            tickers.sort()
            shown_tickers = tickers[:tickers_to_show]
            
            formatted_parts.append(f"**{asset_class.upper()}:**")
            formatted_parts.append(", ".join(f"`{t}`" for t in shown_tickers))
            
            if len(tickers) > tickers_to_show:
                remaining = len(tickers) - tickers_to_show
                formatted_parts.append(f"*...and {remaining} more*")
            
            formatted_parts.append("")  # Empty line between groups
            total_shown += tickers_to_show

        return "\n".join(formatted_parts).strip()

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Send symbols to Discord webhook."""
        symbols: list[AssetSymbol] = inputs.get("symbols", [])
        
        if not symbols:
            logger.info("DiscordOutput: No symbols provided, skipping Discord notification")
            return {"status": "Skipped (no symbols)"}

        # Get Discord webhook URL from vault
        webhook_url = APIKeyVault().get("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("DiscordOutput: DISCORD_WEBHOOK_URL not set, skipping Discord notification")
            return {"status": "Skipped (no webhook URL configured)"}

        # Get parameters
        message_template = self.params.get("message_template", self.default_params["message_template"])
        max_display = self.params.get("max_symbols_display", 50)

        # Format symbol list
        symbol_list_formatted = self._format_symbol_list(symbols, max_display)
        
        # Build message
        message_content = message_template.format(
            symbol_list=symbol_list_formatted,
            count=len(symbols)
        )

        # Discord has a 2000 character limit per message
        if len(message_content) > 2000:
            # Truncate and add warning
            message_content = message_content[:1950] + "\n\n*...message truncated (too long)*"

        # Send to Discord
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "content": message_content,
                    "username": "Fig Nodes Bot"
                }
                
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"DiscordOutput: Successfully sent {len(symbols)} symbols to Discord")
                    return {"status": f"Success: {len(symbols)} symbols sent to Discord"}
                else:
                    error_msg = f"Discord API error: {response.status_code}"
                    logger.error(f"DiscordOutput: {error_msg}")
                    return {"status": f"Error: {error_msg}"}
                    
        except httpx.TimeoutException:
            logger.error("DiscordOutput: Request to Discord timed out")
            return {"status": "Error: Request timed out"}
        except Exception as e:
            logger.error(f"DiscordOutput: Failed to send to Discord: {e}")
            return {"status": f"Error: {str(e)}"}

