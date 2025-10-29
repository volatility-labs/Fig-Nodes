# Discord Webhook Setup

This guide shows you how to set up Discord notifications for Fig Nodes.

## Step 1: Create a Discord Webhook

1. Open Discord and go to your desired channel
2. Click the gear icon ⚙️ next to the channel name (Edit Channel)
3. Go to **Integrations** → **Webhooks**
4. Click **New Webhook** or **Create Webhook**
5. Give it a name (e.g., "Fig Nodes Bot")
6. Copy the **Webhook URL** (it looks like: `https://discord.com/api/webhooks/...`)

## Step 2: Add Webhook URL to Fig Nodes

### Option 1: Via UI (Recommended)
1. Open Fig Nodes in your browser: http://localhost:5173/static/
2. Click the **Settings** icon (⚙️) in the top right
3. Go to **API Keys** section
4. Add a new key:
   - **Key Name**: `DISCORD_WEBHOOK_URL`
   - **Value**: Paste your webhook URL
5. Click **Save**

### Option 2: Via .env File
Create or edit `.env` file in the project root:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

## Step 3: Use Discord Output Node

1. In your workflow, add a **Discord Output** node
2. Connect your symbol list to the Discord Output node input
3. Customize the message template (optional):
   - Use `{symbol_list}` placeholder for the symbols
   - Use `{count}` placeholder for the total count
4. Set max symbols to display (default: 50)
5. Execute your workflow!

## Example Workflow

```
Polygon Universe
    ↓
[Filter Nodes]
    ↓
Discord Output  →  Discord Channel! 📨
```

## Message Format

The default message looks like:

```
📊 **Trading Symbols Update**

**STOCKS:**
`AAPL`, `GOOGL`, `MSFT`, `TSLA`

**CRYPTO:**
`BTC`, `ETH`

*Total: 6 symbols*
```

## Optional Feature

The Discord Output node is **completely optional**:
- If `DISCORD_WEBHOOK_URL` is not set, the node will skip silently
- Your workflow will continue to run normally
- No errors will be thrown

## Troubleshooting

### "Skipped (no webhook URL configured)"
- You haven't set the `DISCORD_WEBHOOK_URL` in settings
- Check API Keys section in Settings

### "Error: Discord API error: 404"
- Your webhook URL is invalid or the webhook was deleted
- Create a new webhook and update the URL

### "Error: Request timed out"
- Discord might be temporarily unavailable
- Check your internet connection

### Messages are truncated
- Discord has a 2000 character limit
- Reduce `max_symbols_display` parameter
- Shorten your message template

## Security Notes

⚠️ **Keep your webhook URL private!**
- Anyone with the webhook URL can send messages to your Discord channel
- Don't commit `.env` file to version control
- Don't share your webhook URL publicly

## Example Message Templates

### Minimal:
```
{symbol_list}
```

### Detailed:
```
🚀 **New Trading Opportunities**

{symbol_list}

📊 Total Symbols: {count}
⏰ Generated: {timestamp}
```

### Alert Style:
```
⚠️ **ALERT: {count} Symbols Match Criteria**

{symbol_list}

✅ Review these symbols before trading
```

---

**Happy Trading! 📈**

