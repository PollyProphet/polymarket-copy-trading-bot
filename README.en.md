# Polymarket Copy Trading Bot

**[中文](README.md) | English**

Automated copy-trading bot for [Polymarket](https://polymarket.com) prediction markets. Monitor target wallets in real time and mirror their trades on your own account with configurable sizing, filters, and risk limits.

---

## Overview

This project watches selected Polymarket wallet addresses, detects new trading activity through the official Data API, and optionally executes mirrored orders through the [Polymarket CLOB API](https://docs.polymarket.com/) via [`py-clob-client`](https://github.com/Polymarket/py-clob-client).

It supports two operating modes:

| Mode | Description |
|------|-------------|
| **Monitor only** | Log target wallet activity; no orders are placed |
| **Copy trading** | Automatically replicate qualifying trades on your wallet |

---

## Features

- **Real-time wallet monitoring** — Polls target addresses and streams activity through an in-memory queue
- **Automated copy trading** — Mirrors BUY/SELL trades based on your strategy
- **Flexible sizing** — Scale mode (percentage of target trade size) with min/max USDC caps
- **Order types** — Market and limit orders
- **Wallet modes** — EOA direct signing or Polymarket proxy wallets (`signature_type` 1/2)
- **On-chain approvals** — Automatic USDC and conditional token approvals for EOA mode
- **Resilience** — Retry with exponential backoff, structured logging, graceful shutdown
- **Proxy support** — Optional HTTP proxy for API and Polygon RPC access

---

## Architecture

```
WalletMonitor  →  Activity Queue  →  CopyTrader  →  OrderExecutor  →  Polymarket CLOB
     │                                      │
     └── Polymarket Data API                └── py-clob-client + Web3 (Polygon)
```

1. `WalletMonitor` polls the Polymarket Data API for new activity on target wallets.
2. Events are published to an `InMemoryActivityQueue` (RabbitMQ planned, not yet implemented).
3. Each configured `CopyTrader` subscribes to a target wallet and applies strategy filters.
4. Qualifying trades are submitted through `OrderExecutor` to the CLOB API.

---

## Requirements

- **Python** 3.13+
- **Network access** to Polymarket APIs and Polygon RPC
- **PostgreSQL** (optional — for checkpoint/trade persistence utilities)
- **HTTP proxy** (optional — if Polymarket is blocked in your region)

---

## Installation

### Option A — uv (recommended)

```bash
git clone https://github.com/PollyProphet/polymarket-copy-trading-bot.git
cd polymarket-copy-trading-bot
uv sync
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows
```

### Option B — pip

```bash
git clone https://github.com/PollyProphet/polymarket-copy-trading-bot.git
cd polymarket-copy-trading-bot
pip install -e .
```

---

## Configuration

### 1. Create config files

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Edit `config.yaml` for monitoring targets and strategy. Store private keys in `.env` — **never commit secrets to Git**.

### 2. Minimal copy-trading setup

```yaml
monitoring:
  wallets:
    - "0xTargetWalletAddress"
  poll_interval_seconds: 5
  batch_size: 100

polymarket_api:
  proxy: "http://localhost:7891"   # optional
  timeout: 30.0
  verify_ssl: true

user_wallets:
  - name: "MyWallet"
    address: "0xYourEOAAddress"
    private_key_env: "MY_WALLET_PRIVATE_KEY"
    signature_type: 0              # 0 = EOA, 1/2 = proxy mode

    copy_strategy:
      min_trigger_amount: 10       # skip target trades below this (USDC)
      min_trade_amount: 0            # floor for your copied trade size
      max_trade_amount: 100          # ceiling for your copied trade size
      order_type: "market"           # market | limit
      copy_mode: "scale"
      scale_percentage: 10.0         # copy 10% of target notional
```

### 3. Set private keys

In `.env`:

```bash
MY_WALLET_PRIVATE_KEY=0xYourPrivateKeyHere
```

Or export the variable in your shell. The name must match `private_key_env` in `config.yaml`.

**Proxy wallet example** (browser / Polymarket proxy):

```yaml
user_wallets:
  - name: "ProxyWallet"
    address: "0xYourEOAAddress"
    proxy_address: "0xYourPolymarketProxyAddress"
    signature_type: 2
    private_key_env: "MY_WALLET_PRIVATE_KEY"
    copy_strategy:
      copy_mode: "scale"
      scale_percentage: 5.0
      order_type: "limit"
```

Verify key ↔ address mapping:

```bash
python verify_key_address.py
```

See [`config.example.yaml`](config.example.yaml) for the full reference.

---

## Running

```bash
python -m src.main
```

Expected startup output:

```
Loaded .env file: .../polymarket-copy-trading-bot/.env
CopyTrader 'MyWallet' initialized | Address: 0x... | Mode: scale
Monitoring running, press Ctrl+C to exit...
```

Press `Ctrl+C` to stop gracefully. Trade statistics are printed on shutdown.

### Monitor-only mode

Omit `user_wallets` or leave it empty. The bot will log activity without placing orders.

---

## Copy Strategies

### Scale mode (recommended)

Copies a fixed percentage of the target trade's USDC notional:

```yaml
copy_mode: "scale"
scale_percentage: 10.0   # target trades $100 → you trade $10
```

### Allocate mode (experimental)

Proportional allocation based on portfolio balance is **not fully implemented** and currently falls back to a 10% scale.

---

## Risk Controls

| Parameter | Purpose |
|-----------|---------|
| `min_trigger_amount` | Ignore target trades below this USDC value |
| `min_trade_amount` | Raise your copied size if the scaled amount is too small |
| `max_trade_amount` | Cap your copied size per trade (`0` = no cap) |
| `order_type` | `market` for immediate fills; `limit` uses the target's price |

**Order semantics**

- **Market BUY** — amount is USDC
- **Market SELL** — amount is converted from USDC to token quantity using the reference price
- **Limit orders** — USDC notional is converted to token size at the limit price

---

## Wallet Signature Types

| `signature_type` | Mode | Notes |
|------------------|------|-------|
| `0` | EOA | Direct signing; on-chain token approvals required |
| `1` | Polymarket proxy | Requires `proxy_address` |
| `2` | Browser wallet proxy | Requires `proxy_address`; complete "Enable Trading" on Polymarket first |

---

## Project Structure

```
polymarket-copy-trading-bot/
├── src/
│   ├── main.py                     # Entry point
│   ├── wallet_monitor.py           # Target wallet polling
│   ├── copy_trader.py              # Copy-trading logic
│   ├── in_memory_activity_queue.py # Event bus
│   ├── config_loader.py            # YAML + env loading
│   ├── trading/order_executor.py   # CLOB order submission
│   └── blockchain/token_approver.py# Polygon approvals (EOA)
├── config.example.yaml
├── .env.example
├── docs/design/                    # Design documents
├── test_*.py                       # Test scripts
└── debug_limit_order.py            # Limit order debugging tool
```

---

## Testing

```bash
python test_copy_trader.py
python test_message_queue.py
python test_min_trade_amount.py
```

Utility scripts:

```bash
python verify_key_address.py      # Validate private key ↔ address
python check_allowance_onchain.py # Check on-chain token allowances
python debug_limit_order.py --help
```

---

## Logging

Logs are written to the `logs/` directory (configurable via `logging.log_dir`).

```bash
# Linux / macOS
tail -f logs/polymarket_bot.log

# Windows PowerShell
Get-Content logs\polymarket_bot.log -Wait
```

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Bot won't start | `config.yaml` syntax; `.env` exists; dependencies installed |
| Private key error | Env var name matches `private_key_env`; key starts with `0x` |
| No copied trades | `min_trigger_amount` too high; activity type is not `TRADE` |
| Order failures | USDC balance; proxy allowance ("Enable Trading"); network/proxy |
| API unreachable | Set `polymarket_api.proxy`; verify SSL settings |

---

## Security

1. **Never** store private keys in `config.yaml` or commit `.env` to version control.
2. Use a **dedicated trading wallet** with limited funds.
3. Start with a **low `scale_percentage`** and small `max_trade_amount`.
4. Review logs regularly and monitor on-chain balances.
5. For production, prefer a secrets manager (AWS Secrets Manager, Vault, etc.) over plain `.env` files.

---

## Documentation

- [Quick Start Guide (中文)](QUICKSTART.md)
- [Copy Trading Design](docs/design/copy-trading-feature-design.md)
- [Wallet Monitor Design](docs/design/wallet-monitor-design-doc.md)
- [Polymarket CLOB API](https://docs.polymarket.com/)
- [py-clob-client](https://github.com/Polymarket/py-clob-client)

---

## Known Limitations

- RabbitMQ queue backend is not implemented (`queue.type: rabbitmq` will raise an error)
- `allocate` copy mode is incomplete
- `limit_order_duration` is configured but not yet applied to submitted orders
- PostgreSQL persistence is available via `DatabaseHandler` but not wired into the main monitoring loop

---

## Disclaimer

This software is provided for **educational and research purposes only**. Trading on prediction markets involves substantial financial risk. You are solely responsible for any losses incurred while using this bot.

- Past performance of copied traders does not guarantee future results
- Only trade with capital you can afford to lose
- Review Polymarket's terms of service and applicable regulations in your jurisdiction

---

## License

See repository license file. If none is present, contact the repository owner for terms of use.
