# cf-mail-api

> Self-hosted temporary mailbox service on **Cloudflare Workers + D1** with your own custom subdomain.
> Use it as a personal disposable-mailbox backend — generate any `xxx@<your-domain>` on the fly, read incoming mail, forward to your real inbox.

| | |
|---|---|
| **License** | GNU GPL-3.0 |
| **Runtime** | Cloudflare Workers (free tier OK) |
| **Storage** | Cloudflare D1 (SQLite) |
| **Inbound** | Cloudflare Email Routing → Worker → D1 + optional forward |
| **Outbound** | Resend API (or any HTTP send provider) |

---

## ⚠️ Before You Deploy — Read This First

> **DO NOT** point this at anyone else's worker URL. **DO NOT** publish your deployed URL publicly. **DO NOT** use the default `*.workers.dev` URL as a shared service.
>
> This project runs on Cloudflare's **free tier** (~100k requests/day). The moment someone else finds your endpoint, they will burn through your quota and **your own mailbox stops working**.
>
> The author of this project **does not** publish a hosted demo. If you find one online claiming to be "the official cf-mail-api", it is **not** us — it is a phishing/abuse mirror. Always deploy your own.

---

## Features

- Generate disposable mailbox addresses on demand: `POST /api/generate-email`
- List mailboxes, list messages, fetch single message, delete, clear
- Inbound webhook ingestion: `POST /api/inbound`
- Auto-forward all inbound mail to your real inbox (e.g. QQ/Gmail) via `FORWARD_TO_EMAIL`
- Optional outbound send via Resend (separate `send.<your-domain>` route)
- Bearer-token / `x-api-key` / `?api_key=` auth
- Plain `curl`-friendly API, no SDK required

---

## Quick Start

### 1. Prerequisites

- A domain managed by Cloudflare (DNS must be on CF — needed for Email Routing)
- A Cloudflare account (free tier is enough)
- `wrangler` CLI: `npm i -g wrangler`
- Node.js 18+

### 2. Clone & configure

```bash
git clone https://github.com/lingion/cf-mail-api.git
cd cf-mail-api
npm install
```

### 3. Create the D1 database

```bash
wrangler d1 create mail_api
# Copy the printed `database_id` into wrangler.toml
wrangler d1 execute mail_api --remote --file=./schema.sql
```

### 4. Configure `wrangler.toml`

Replace **every** `<your-domain>` placeholder with your own CF-managed domain. Replace `<your-d1-database-id>`, `<your-api-token>`, `<your-real-inbox@example.com>` with your own values.

The **mailbox receiving domain** (`mail.<your-domain>`) and the **API domain** (`api.<your-domain>`) and the **send domain** (`send.<your-domain>`) should all live under one zone you control.

```toml
# Example (DO NOT copy these values literally):
[[routes]]
pattern = "api.example.com/*"
zone_name = "example.com"

[vars]
MAIL_DOMAIN = "mail.example.com"
API_TOKEN = "<generate-with: openssl rand -hex 32>"
FORWARD_TO_EMAIL = "you@gmail.com"
```

### 5. Enable Cloudflare Email Routing

In the Cloudflare dashboard for your zone:

1. **Email → Email Routing → Enable**
2. Add a destination address (your real inbox) and verify it
3. Add a catch-all route: `*@mail.<your-domain>` → **Send to Worker** → select `cf-mail-api`

The Worker handles the rest — writes to D1, optionally forwards.

### 6. Deploy

```bash
wrangler deploy
```

After deploy, your private API lives at `https://api.<your-domain>/` — **don't share it**.

---

## API Reference

> All endpoints require auth via one of:
> `Authorization: Bearer <API_TOKEN>` · `x-api-key: <API_TOKEN>` · `?api_key=<API_TOKEN>`

### Health check

```bash
curl https://api.<your-domain>/health
```

### Generate a mailbox

```bash
curl -X POST https://api.<your-domain>/api/generate-email \
  -H 'x-api-key: <API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"prefix":"task_20260630_ab12","label":"signup","ttl_hours":24}'
```

Optional fields:

| field | rule |
|---|---|
| `prefix` / `name` | optional, must match `^[a-z0-9_-]{6,40}$` if provided |
| `label` | free-form tag |
| `ttl_hours` | mailbox lifetime, default 24h |

Response:

```json
{
  "success": true,
  "data": {
    "mailbox_id": "task_20260630_ab12",
    "email": "task_20260630_ab12@mail.<your-domain>",
    "domain": "mail.<your-domain>",
    "token": "...",
    "created_at": "...",
    "expires_at": "..."
  }
}
```

### List messages for a mailbox

```bash
curl 'https://api.<your-domain>/api/mailboxes/<mailbox_id>/messages' \
  -H 'x-api-key: <API_TOKEN>'
```

### Fetch / delete a single message

```bash
curl 'https://api.<your-domain>/api/email/<message_id>'  -H 'x-api-key: <API_TOKEN>'
curl -X DELETE 'https://api.<your-domain>/api/email/<message_id>' -H 'x-api-key: <API_TOKEN>'
```

### Clear all mail for an address

```bash
curl -X DELETE 'https://api.<your-domain>/api/emails/clear?email=<addr>@mail.<your-domain>' \
  -H 'x-api-key: <API_TOKEN>'
```

### Stats

```bash
curl 'https://api.<your-domain>/api/stats' -H 'x-api-key: <API_TOKEN>'
```

### Inbound webhook (for external senders)

```bash
curl -X POST 'https://api.<your-domain>/api/inbound' \
  -H 'x-api-key: <API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{
    "from": "alice@example.org",
    "to": "task_20260630_ab12@mail.<your-domain>",
    "subject": "Verify your account",
    "text": "Click here to verify..."
  }'
```

Supported inbound fields: `id` / `external_id`, `from` / `from_addr`, `to` / `to_addr` / `recipient`, `subject`, `text` / `text_body`, `html` / `html_body`.

---

## Sending Email (optional)

If you want to **send** mail from a temp address too, configure a third route `send.<your-domain>` and set a Resend API key in `wrangler.toml`:

```toml
[vars]
RESEND_API_KEY = "<your-resend-api-key>"
```

Then:

```bash
curl -X POST https://send.<your-domain>/api/send \
  -H 'x-api-key: <API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{
    "from":    "task_20260630_ab12@mail.<your-domain>",
    "to":      "bob@example.org",
    "subject": "Hello from a temp mailbox",
    "text":    "This message was sent via cf-mail-api."
  }'
```

**Note:** `from` must be a mailbox that already exists in your D1, and the domain must have a valid SPF/DKIM record for deliverability.

---

## Configuration Cheatsheet

| Env var | Purpose |
|---|---|
| `MAIL_DOMAIN` | The `<subdomain>.<your-domain>` that receives mail |
| `API_TOKEN` | Bearer token for the public API (rotate periodically) |
| `FORWARD_TO_EMAIL` | (optional) Where to forward inbound mail |
| `RESEND_API_KEY` | (optional) Outbound provider; only needed if you enable send |

---

## Cost & Quota

This project is designed to run entirely on Cloudflare's **free tier**:

| Resource | Free tier |
|---|---|
| Workers requests | 100,000 / day |
| D1 reads | 5,000,000 / day |
| D1 writes | 100,000 / day |
| Email Routing messages | 100 / day (per destination) |

**Do not** expose this service publicly. Every external request consumes your quota. If you need more headroom, put an auth layer in front (a per-user token, IP allowlist, or rate limit) — the auth flag is already there, just don't share the token.

---

## Project Structure

```
cf-mail-api/
├── LICENSE              # GNU GPL-3.0
├── README.md            # this file
├── package.json
├── schema.sql           # D1 schema
├── wrangler.toml        # worker config (replace placeholders!)
├── src/
│   ├── index.js         # main worker (inbound + mailbox API)
│   └── send.js          # outbound send route
└── cloudflare_mail_client.py  # optional Python client
```

---

## License

GNU General Public License v3.0. See [LICENSE](./LICENSE).

In short: you can use, modify, and redistribute this freely — including commercially — but **any derivative work must also be GPL-3.0** and **must keep the copyright notice**. There is no warranty.

---

## Contributing

PRs welcome at <https://github.com/lingion/cf-mail-api>. By contributing you agree your contribution is also licensed under GPL-3.0.

---

# cf-mail-api — 中文说明

> 基于 **Cloudflare Workers + D1** 自建临时邮箱服务，使用你自己的自定义子域名。
> 把它当作个人可丢弃邮箱后端：随时生成 `xxx@<你的域名>`，收件、转发、读取一站式搞定。

| | |
|---|---|
| **许可证** | GNU GPL-3.0 |
| **运行平台** | Cloudflare Workers（免费额度即可） |
| **存储** | Cloudflare D1（SQLite） |
| **收件** | Cloudflare Email Routing → Worker → D1 + 可选转发 |
| **发件** | Resend API（或其他 HTTP 发件服务商） |

---

## ⚠️ 部署前必读

> **不要**把任何人的 worker URL 拿来直接用。**不要**把部署好的 URL 发到任何公开渠道。**不要**用默认的 `*.workers.dev` 当公共邮箱服务。
>
> 本项目运行在 Cloudflare **免费额度**（约 10 万请求/天）。一旦别人找到你的端点，你的额度会被瞬间刷光，**你自己的邮箱就直接挂了**。
>
> 本项目作者 **不提供** 任何官方在线 demo。如果你在网上看到一个号称「官方 cf-mail-api」的站点，那不是我们——那是钓鱼/滥用镜像。永远自己部署。

---

## 功能特性

- 按需生成可丢弃邮箱地址：`POST /api/generate-email`
- 列出邮箱、列出邮件、读取单封、删除、清空
- 入站 webhook 摄取：`POST /api/inbound`
- 自动把所有入站邮件转发到你的真实邮箱（如 QQ/Gmail），通过 `FORWARD_TO_EMAIL` 配置
- 可选发件功能（Resend，独立 `send.<你的域名>` 路由）
- 支持 Bearer token / `x-api-key` / `?api_key=` 三种鉴权
- 纯 `curl` 友好，无需 SDK

---

## 快速开始

### 1. 准备

- 一个由 Cloudflare 托管的域名（DNS 必须在 CF 上，因为要用 Email Routing）
- 一个 Cloudflare 账号（免费版即可）
- `wrangler` CLI：`npm i -g wrangler`
- Node.js 18+

### 2. 克隆 & 安装

```bash
git clone https://github.com/lingion/cf-mail-api.git
cd cf-mail-api
npm install
```

### 3. 创建 D1 数据库

```bash
wrangler d1 create mail_api
# 把打印出来的 database_id 填到 wrangler.toml
wrangler d1 execute mail_api --remote --file=./schema.sql
```

### 4. 配置 `wrangler.toml`

把 **所有** `<你的域名>` 占位符换成你自己 CF 托管的域名。把 `<your-d1-database-id>`、`<your-api-token>`、`<your-real-inbox@example.com>` 换成你自己的值。

**收件子域** (`mail.<你的域名>`)、**API 子域** (`api.<你的域名>`)、**发件子域** (`send.<你的域名>`) 必须在同一个 zone 下，且都在你自己名下。

```toml
# 示例（请勿直接复制这些值）：
[[routes]]
pattern = "api.example.com/*"
zone_name = "example.com"

[vars]
MAIL_DOMAIN = "mail.example.com"
API_TOKEN = "<用 openssl rand -hex 32 生成>"
FORWARD_TO_EMAIL = "you@gmail.com"
```

### 5. 启用 Cloudflare Email Routing

在 Cloudflare 控制台你的域名下：

1. **Email → Email Routing → Enable**
2. 添加一个目标地址（你的真实邮箱）并完成验证
3. 添加 catch-all 路由：`*@mail.<你的域名>` → **Send to Worker** → 选 `cf-mail-api`

Worker 会负责剩下的事——写入 D1、可选转发。

### 6. 部署

```bash
wrangler deploy
```

部署完成后，你的私有 API 在 `https://api.<你的域名>/`——**不要告诉任何人**。

---

## API 参考

> 所有接口需要鉴权，三选一：
> `Authorization: Bearer <API_TOKEN>` · `x-api-key: <API_TOKEN>` · `?api_key=<API_TOKEN>`

### 健康检查

```bash
curl https://api.<你的域名>/health
```

### 生成邮箱

```bash
curl -X POST https://api.<你的域名>/api/generate-email \
  -H 'x-api-key: <API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"prefix":"task_20260630_ab12","label":"注册测试","ttl_hours":24}'
```

可选字段：

| 字段 | 规则 |
|---|---|
| `prefix` / `name` | 可选，若提供须匹配 `^[a-z0-9_-]{6,40}$` |
| `label` | 自由标签 |
| `ttl_hours` | 邮箱有效期，默认 24 小时 |

响应：

```json
{
  "success": true,
  "data": {
    "mailbox_id": "task_20260630_ab12",
    "email": "task_20260630_ab12@mail.<你的域名>",
    "domain": "mail.<你的域名>",
    "token": "...",
    "created_at": "...",
    "expires_at": "..."
  }
}
```

### 列出邮箱下的邮件

```bash
curl 'https://api.<你的域名>/api/mailboxes/<mailbox_id>/messages' \
  -H 'x-api-key: <API_TOKEN>'
```

### 读取/删除单封邮件

```bash
curl 'https://api.<你的域名>/api/email/<message_id>'  -H 'x-api-key: <API_TOKEN>'
curl -X DELETE 'https://api.<你的域名>/api/email/<message_id>' -H 'x-api-key: <API_TOKEN>'
```

### 清空某个邮箱下的所有邮件

```bash
curl -X DELETE 'https://api.<你的域名>/api/emails/clear?email=<addr>@mail.<你的域名>' \
  -H 'x-api-key: <API_TOKEN>'
```

### 统计

```bash
curl 'https://api.<你的域名>/api/stats' -H 'x-api-key: <API_TOKEN>'
```

### 入站 webhook（外部发件方）

```bash
curl -X POST 'https://api.<你的域名>/api/inbound' \
  -H 'x-api-key: <API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{
    "from": "alice@example.org",
    "to": "task_20260630_ab12@mail.<你的域名>",
    "subject": "验证你的账号",
    "text": "点击链接验证..."
  }'
```

支持字段：`id` / `external_id`，`from` / `from_addr`，`to` / `to_addr` / `recipient`，`subject`，`text` / `text_body`，`html` / `html_body`。

---

## 发件功能（可选）

如果你想从临时邮箱 **发信**，再开第三个路由 `send.<你的域名>`，并在 `wrangler.toml` 设置 Resend API key：

```toml
[vars]
RESEND_API_KEY = "<你的-resend-api-key>"
```

然后：

```bash
curl -X POST https://send.<你的域名>/api/send \
  -H 'x-api-key: <API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{
    "from":    "task_20260630_ab12@mail.<你的域名>",
    "to":      "bob@example.org",
    "subject": "来自临时邮箱的问候",
    "text":    "这封邮件通过 cf-mail-api 发出。"
  }'
```

**注意**：`from` 必须是 D1 里已存在的 mailbox，且域名要有合法的 SPF/DKIM 记录才能保证送达率。

---

## 配置速查

| 环境变量 | 用途 |
|---|---|
| `MAIL_DOMAIN` | 收件用的 `<子域名>.<你的域名>` |
| `API_TOKEN` | 公共 API 的 Bearer token（定期轮换） |
| `FORWARD_TO_EMAIL` | （可选）所有入站邮件转发到此 |
| `RESEND_API_KEY` | （可选）发件服务商 key，仅开启发件时需要 |

---

## 成本 & 配额

本项目设计为完全跑在 Cloudflare **免费额度**内：

| 资源 | 免费额度 |
|---|---|
| Workers 请求 | 100,000 / 天 |
| D1 读 | 5,000,000 / 天 |
| D1 写 | 100,000 / 天 |
| Email Routing 邮件 | 100 / 天（每个目标地址） |

**切勿**把此服务对外公开。每个外部请求都在消耗你的配额。如果你需要更大空间，请在前面加一层鉴权（每个用户独立 token、IP 白名单、或速率限制）——鉴权开关项目里已经预留好，别分享 token 就行。

---

## 目录结构

```
cf-mail-api/
├── LICENSE              # GNU GPL-3.0
├── README.md            # 本文件
├── package.json
├── schema.sql           # D1 schema
├── wrangler.toml        # worker 配置（请替换占位符！）
├── src/
│   ├── index.js         # 主 worker（收件 + 邮箱 API）
│   └── send.js          # 发件路由
└── cloudflare_mail_client.py  # 可选 Python 客户端
```

---

## 许可证

GNU 通用公共许可证 v3.0。详见 [LICENSE](./LICENSE)。

简言之：你可以自由使用、修改、再分发——包括商业用途——但**任何衍生作品也必须 GPL-3.0** 且**必须保留版权声明**。无任何担保。

---

## 贡献

欢迎在 <https://github.com/lingion/cf-mail-api> 提 PR。提交贡献即视为同意同样以 GPL-3.0 授权。