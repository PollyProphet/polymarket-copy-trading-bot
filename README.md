# Polymarket 复制交易机器人

**中文 | [English](README.en.md)**

面向 [Polymarket](https://polymarket.com) 预测市场的自动化复制交易工具。实时监控目标钱包交易活动，并按可配置的规则在你的账户上自动跟单。

---

## 项目简介

本工具通过 Polymarket 官方 Data API 轮询目标钱包的新交易，并可选地通过 [Polymarket CLOB API](https://docs.polymarket.com/) 与 [`py-clob-client`](https://github.com/Polymarket/py-clob-client) 在你的钱包上执行镜像订单。

支持两种运行模式：

| 模式 | 说明 |
|------|------|
| **仅监控** | 记录目标钱包活动，不提交任何订单 |
| **复制交易** | 自动复制符合条件的交易到你的钱包 |

---

## 功能特性

- **实时钱包监控** — 轮询目标地址，通过内存队列分发活动事件
- **自动复制交易** — 按策略镜像 BUY/SELL 交易
- **灵活仓位控制** — Scale 模式（按目标成交额百分比）配合最小/最大 USDC 限制
- **多种订单类型** — 支持市价单与限价单
- **多种钱包模式** — EOA 直连签名或 Polymarket 代理钱包（`signature_type` 1/2）
- **链上授权** — EOA 模式下自动完成 USDC 与条件代币授权
- **容错机制** — 指数退避重试、结构化日志、优雅退出
- **代理支持** — API 与 Polygon RPC 均可配置 HTTP 代理

---

## 系统架构

```
WalletMonitor  →  Activity Queue  →  CopyTrader  →  OrderExecutor  →  Polymarket CLOB
     │                                      │
     └── Polymarket Data API                └── py-clob-client + Web3 (Polygon)
```

1. `WalletMonitor` 轮询 Data API，获取目标钱包的新活动。
2. 事件发布到 `InMemoryActivityQueue`（RabbitMQ 已规划，尚未实现）。
3. 每个 `CopyTrader` 订阅目标钱包并执行策略过滤。
4. 符合条件的交易由 `OrderExecutor` 提交至 CLOB API。

---

## 环境要求

- **Python** 3.13+
- 可访问 Polymarket API 与 Polygon RPC 的网络环境
- **PostgreSQL**（可选 — 用于检查点/交易持久化工具）
- **HTTP 代理**（可选 — 部分地区访问 Polymarket 需要）

---

## 安装

### 方式 A — uv（推荐）

```bash
git clone https://github.com/PollyProphet/polymarket-copy-trading-bot.git
cd polymarket-copy-trading-bot
uv sync
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows
```

### 方式 B — pip

```bash
git clone https://github.com/PollyProphet/polymarket-copy-trading-bot.git
cd polymarket-copy-trading-bot
pip install -e .
```

---

## 配置

### 1. 创建配置文件

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

在 `config.yaml` 中配置监控目标与策略。**私钥请写入 `.env`，切勿提交到 Git。**

### 2. 最小复制交易配置

```yaml
monitoring:
  wallets:
    - "0xTargetWalletAddress"
  poll_interval_seconds: 5
  batch_size: 100

polymarket_api:
  proxy: "http://localhost:7891"   # 可选
  timeout: 30.0
  verify_ssl: true

user_wallets:
  - name: "MyWallet"
    address: "0xYourEOAAddress"
    private_key_env: "MY_WALLET_PRIVATE_KEY"
    signature_type: 0              # 0 = EOA，1/2 = 代理模式

    copy_strategy:
      min_trigger_amount: 10       # 目标交易低于此值（USDC）则跳过
      min_trade_amount: 0            # 我方单笔跟单下限
      max_trade_amount: 100          # 我方单笔跟单上限
      order_type: "market"           # market | limit
      copy_mode: "scale"
      scale_percentage: 10.0         # 跟单目标成交额的 10%
```

### 3. 设置私钥

在 `.env` 中：

```bash
MY_WALLET_PRIVATE_KEY=0xYourPrivateKeyHere
```

或在 shell 中导出环境变量。变量名须与 `config.yaml` 中的 `private_key_env` 一致。

**代理钱包示例**（浏览器 / Polymarket 代理）：

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

验证私钥与地址是否匹配：

```bash
python verify_key_address.py
```

完整配置说明见 [`config.example.yaml`](config.example.yaml)。

---

## 运行

```bash
python -m src.main
```

正常启动时输出类似：

```
Loaded .env file: .../polymarket-copy-trading-bot/.env
CopyTrader 'MyWallet' initialized | Address: 0x... | Mode: scale
Monitoring running, press Ctrl+C to exit...
```

按 `Ctrl+C` 优雅退出，程序会打印交易统计。

### 仅监控模式

不配置 `user_wallets` 或留空即可。程序只记录活动，不提交订单。

---

## 复制策略

### Scale 模式（推荐）

按目标交易 USDC 成交额的固定比例跟单：

```yaml
copy_mode: "scale"
scale_percentage: 10.0   # 目标交易 $100 → 你交易 $10
```

### Allocate 模式（实验性）

按资产比例分配的功能**尚未完整实现**，当前会回退为 10% 的 Scale 逻辑。

---

## 风险控制

| 参数 | 作用 |
|------|------|
| `min_trigger_amount` | 忽略低于此 USDC 值的目标交易 |
| `min_trade_amount` | 缩放后金额过小时，抬升我方跟单金额 |
| `max_trade_amount` | 限制我方单笔跟单上限（`0` 表示不限制） |
| `order_type` | `market` 即时成交；`limit` 使用目标成交价 |

**订单语义说明**

- **市价 BUY** — 金额为 USDC
- **市价 SELL** — 按参考价格将 USDC 换算为代币数量
- **限价单** — 按限价将 USDC 名义金额换算为代币数量

---

## 钱包签名类型

| `signature_type` | 模式 | 说明 |
|------------------|------|------|
| `0` | EOA | 私钥直接签名；需链上代币授权 |
| `1` | Polymarket 代理 | 需配置 `proxy_address` |
| `2` | 浏览器钱包代理 | 需配置 `proxy_address`；先在 Polymarket 完成「Enable Trading」 |

---

## 项目结构

```
polymarket-copy-trading-bot/
├── src/
│   ├── main.py                     # 程序入口
│   ├── wallet_monitor.py           # 目标钱包轮询
│   ├── copy_trader.py              # 复制交易逻辑
│   ├── in_memory_activity_queue.py # 内存事件队列
│   ├── config_loader.py            # 配置与环境变量加载
│   ├── trading/order_executor.py   # CLOB 订单提交
│   └── blockchain/token_approver.py# Polygon 链上授权（EOA）
├── config.example.yaml
├── .env.example
├── docs/design/                    # 设计文档
├── test_*.py                       # 测试脚本
└── debug_limit_order.py            # 限价单调试工具
```

---

## 测试

```bash
python test_copy_trader.py
python test_message_queue.py
python test_min_trade_amount.py
```

辅助工具：

```bash
python verify_key_address.py      # 验证私钥与地址
python check_allowance_onchain.py # 检查链上代币授权
python debug_limit_order.py --help
```

---

## 日志

日志默认写入 `logs/` 目录（可通过 `logging.log_dir` 配置）。

```bash
# Linux / macOS
tail -f logs/polymarket_bot.log

# Windows PowerShell
Get-Content logs\polymarket_bot.log -Wait
```

日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR`。

---

## 故障排查

| 问题 | 排查方向 |
|------|----------|
| 程序无法启动 | `config.yaml` 语法；`.env` 是否存在；依赖是否安装 |
| 私钥错误 | 环境变量名是否与 `private_key_env` 一致；是否以 `0x` 开头 |
| 没有跟单 | `min_trigger_amount` 是否过高；活动类型是否为 `TRADE` |
| 下单失败 | USDC 余额；代理授权（Enable Trading）；网络/代理 |
| API 无法访问 | 配置 `polymarket_api.proxy`；检查 SSL 设置 |

---

## 安全建议

1. **切勿**将私钥写入 `config.yaml` 或提交 `.env` 到版本库。
2. 使用**专用交易钱包**，仅存放可承受损失的资金。
3. 先用**较低的 `scale_percentage`** 和较小的 `max_trade_amount` 测试。
4. 定期查看日志并监控链上余额。
5. 生产环境建议使用密钥管理服务（AWS Secrets Manager、Vault 等），而非明文 `.env`。

---

## 相关文档

- [快速启动指南](QUICKSTART.md)
- [复制交易设计文档](docs/design/copy-trading-feature-design.md)
- [钱包监控设计文档](docs/design/wallet-monitor-design-doc.md)
- [Polymarket CLOB API](https://docs.polymarket.com/)
- [py-clob-client](https://github.com/Polymarket/py-clob-client)

---

## 已知限制

- RabbitMQ 队列后端尚未实现（`queue.type: rabbitmq` 会报错）
- `allocate` 复制模式未完成
- `limit_order_duration` 已配置但尚未应用到提交的订单
- PostgreSQL 持久化（`DatabaseHandler`）存在，但未接入主监控流程

---

## 免责声明

本软件仅供**学习与研究**使用。预测市场交易存在较高财务风险，使用本工具产生的任何损失由使用者自行承担。

- 被复制交易者的历史表现不代表未来收益
- 请仅使用可承受损失的资金
- 使用前请了解 Polymarket 服务条款及所在地区的相关法规

---

## 许可证

请参阅仓库中的许可证文件。如未提供，请联系仓库维护者了解使用条款。
