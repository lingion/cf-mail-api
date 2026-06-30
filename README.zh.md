<p align="center">
  <a href="https://img.shields.io/github/stars/lingion/cf-mail-api?style=for-the-badge&logo=github&color=FFD700"><img src="https://img.shields.io/github/stars/lingion/cf-mail-api?style=for-the-badge&logo=github&color=FFD700" alt="Stars"></a>
  <a href="https://github.com/lingion/cf-mail-api/network/members"><img src="https://img.shields.io/github/forks/lingion/cf-mail-api?style=for-the-badge&logo=github&color=8B5CF6" alt="Forks"></a>
  <a href="https://github.com/lingion/cf-mail-api/issues"><img src="https://img.shields.io/github/issues/lingion/cf-mail-api?style=for-the-badge&logo=github&color=EF4444" alt="Issues"></a>
  <a href="https://github.com/lingion/cf-mail-api/blob/main/LICENSE"><img src="https://img.shields.io/github/license/lingion/cf-mail-api?style=for-the-badge&logo=github&color=10B981" alt="License"></a>
  <br>
  <a href="https://github.com/lingion/cf-mail-api/commits/main"><img src="https://img.shields.io/github/last-commit/lingion/cf-mail-api?style=flat-square" alt="Last commit"></a>
  <img src="https://img.shields.io/badge/runtime-Cloudflare%20Workers-F38020?style=flat-square&logo=cloudflare&logoColor=white" alt="CF Workers">
  <img src="https://img.shields.io/badge/storage-Cloudflare%20D1-FF7043?style=flat-square&logo=cloudflare&logoColor=white" alt="D1">
  <img src="https://img.shields.io/badge/lang-JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black" alt="JS">
  <a href="README.md"><img src="https://img.shields.io/badge/README-English-0078D4?style=flat-square" alt="English"></a>
</p>

<h1 align="center">cf-mail-api</h1>

<p align="center">
  基于 Cloudflare Workers + D1 的 HTTP webhook 邮件存储后端。<br>
  通过 <code>POST /api/inbound</code> 存入邮件，通过同一套 API 读出。
</p>

---

## 概述

`cf-mail-api` 将邮件消息存储在 Cloudflare D1 数据库中，并通过 HTTP 接口暴露。

存入路径是一次 HTTP 调用：`POST /api/inbound`。该路径不需要任何 DNS 记录、MX 记录或可接收 SMTP 的真实域名。所谓「邮箱地址」(`xxx@mail.<你的域名>`) 只是 D1 里的一行字符串；域名那部分不需要真实可收信。

仓库另外包含三项独立于 webhook 路径的可选功能：

- 可选的 Cloudflare Email Routing 集成，允许真实 SMTP 投递被分发到同一个 worker。
- 可选的 `FORWARD_TO_EMAIL` 变量，用于将入站邮件副本转发到第二个地址。
- 可选的、基于 Resend 的发件路由，部署在第三个子域。

这三项均在 [可选扩展](#可选扩展) 一节中说明。

---

## 仓库结构

| 组件 | 用途 |
|---|---|
| `src/index.js` | 主 worker——`POST /api/inbound` 与邮箱查询 API |
| `src/send.js` | 可选的发件路由（Resend） |
| `schema.sql` | D1 数据库结构（mailboxes / messages） |
| `wrangler.toml` | Worker 配置——部署前必须替换占位符 |
| `cloudflare_mail_client.py` | 可选 Python 客户端 |
| `LICENSE` | GNU GPL-3.0 |
| `README.md` | English documentation |
| `README.zh.md` | 中文文档（本文件） |

---

## 技术栈

| 层 | 选型 |
|---|---|
| 运行时 | Cloudflare Workers（V8 isolates） |
| 存储 | Cloudflare D1（SQLite） |
| 入站（核心） | HTTP webhook |
| 入站（可选） | Cloudflare Email Routing |
| 发件（可选） | Resend HTTP API |
| 鉴权 | Bearer token / `x-api-key` / `?_api_key=*** |
| 客户端（可选） | Python 3（`requests`） |

worker 无 Node 依赖、无构建步骤。`wrangler deploy` 是唯一必需的部署命令。

---

## 快速开始

### 1. 准备

- 一个 Cloudflare 账号（免费版即可）
- `wrangler` CLI：`npm i -g wrangler`
- Node.js 18+
- 核心 webhook 路径不需要域名。默认的 `*.workers.dev` 路由足以满足个人使用。

### 2. 克隆与安装

```bash
git clone https://github.com/lingion/cf-mail-api.git
cd cf-mail-api
npm install
```

### 3. 创建 D1 数据库

```bash
wrangler d1 create mail_api
# 将打印的 `database_id` 填入 wrangler.toml
wrangler d1 execute mail_api --remote --file=./schema.sql
```

### 4. 配置 `wrangler.toml`

唯一必需的环境变量是 `API_TOKEN`。其余变量均为可选，对应下文某一可选扩展。

```toml
# 最小配置——替换 <your-d1-database-id> 与 <your-api-token>：
name = "cf-mail-api"
main = "src/index.js"
compatibility_date = "2026-03-22"

[[d1_databases]]
binding = "DB"
database_name = "mail_api"
database_id = "<your-d1-database-id>"

[vars]
API_TOKEN = "<openssl rand -hex 32>"
```

自定义域名路由仅在使用 Email Routing 扩展时才需要（见下文）。

### 5. 部署

```bash
wrangler deploy
```

### 6. 烟雾测试

```bash
# 健康检查
curl https://<your-worker>.<your-subdomain>.workers.dev/health

# 生成 mailbox（可选——webhook 接受任意地址）
curl -X POST https://<your-worker>.<your-subdomain>.workers.dev/api/generate-email \
  -H 'x-api-key: ***' \
  -H 'Content-Type: application/json' \
  -d '{"prefix":"task_demo01","label":"注册测试","ttl_hours":24}'

# 通过 webhook 存入一封邮件
curl -X POST https://<your-worker>.<your-subdomain>.workers.dev/api/inbound \
  -H 'x-api-key: ***' \
  -H 'Content-Type: application/json' \
  -d '{
    "from":    "noreply@example.org",
    "to":      "task_demo01@mail.<your-domain>",
    "subject": "验证你的账号",
    "text":    "点击链接验证..."
  }'

# 读回
curl 'https://<your-worker>.<your-subdomain>.workers.dev/api/emails?email=task_demo01@mail.<your-domain>' \
  -H 'x-api-key: ***'
```

---

## API 参考

所有接口需要鉴权，三选一：

- `Authorization: Bearer <API_TOKEN>`
- `x-api-key: ***`
- `?api_key=<API_TOKEN>`

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 健康检查 |
| POST | `/api/generate-email` | 创建 mailbox 记录 |
| GET | `/api/mailboxes` | 列出所有 mailbox |
| GET | `/api/mailboxes/:id/messages` | 列出 mailbox 下的邮件 |
| GET | `/api/mailboxes/:id/messages/:msg_id` | 读取单封邮件 |
| GET | `/api/emails?email=...` | 按地址列出邮件 |
| GET | `/api/email/:id` | 按 id 读取单封 |
| DELETE | `/api/email/:id` | 删除单封 |
| DELETE | `/api/emails/clear?email=...` | 清空某地址下的所有邮件 |
| GET | `/api/stats` | mailbox 与邮件计数 |
| POST | `/api/inbound` | Webhook——将邮件存入 D1 |

### POST /api/inbound

```bash
curl -X POST https://<your-worker>.<your-subdomain>.workers.dev/api/inbound \
  -H 'x-api-key: ***' \
  -H 'Content-Type: application/json' \
  -d '{
    "from":    "alice@example.org",
    "to":      "task_demo01@mail.<your-domain>",
    "subject": "验证你的账号",
    "text":    "点击链接验证...",
    "html":    "<a href=\"...\">验证</a>"
  }'
```

请求字段（仅 `to` 必填）：

| 字段 | 别名 | 说明 |
|---|---|---|
| `to` | `to_addr`, `recipient` | 目标 mailbox 地址。字符串或数组；取首个元素。 |
| `from` | `from_addr` | 发件人。字符串或数组；取首个元素。 |
| `subject` | — | 邮件主题。 |
| `text` | `text_body`, `body` | 纯文本正文。 |
| `html` | `html_body` | HTML 正文。 |
| `id` | `external_id` | 可选的外部消息 id，用于关联。 |

若 `to` 在 D1 中无对应 mailbox，worker 会创建一个。因此 webhook 接受发往任意地址的邮件，无论该地址是否事先注册。

### POST /api/generate-email

```bash
curl -X POST https://<your-worker>.<your-subdomain>.workers.dev/api/generate-email \
  -H 'x-api-key: ***' \
  -H 'Content-Type: application/json' \
  -d '{"prefix":"task_demo01","label":"注册测试","ttl_hours":24}'
```

| 字段 | 规则 |
|---|---|
| `prefix` / `name` | 可选。若提供须匹配 `^[a-z0-9_-]{6,40}$`。 |
| `label` | 可选的自由标签。 |
| `ttl_hours` | 可选的 mailbox 有效期（小时），默认 24。 |

该接口用于创建带元数据的 mailbox 记录。它不是接收邮件的前置条件——webhook 接受任意地址。

### GET 接口

```bash
# 某地址下的邮件
curl 'https://<your-worker>.<your-subdomain>.workers.dev/api/emails?email=task_demo01@mail.<your-domain>' \
  -H 'x-api-key: ***'

# 按 id 取单封
curl 'https://<your-worker>.<your-subdomain>.workers.dev/api/email/<message_id>' \
  -H 'x-api-key: ***'

# 所有 mailbox
curl 'https://<your-worker>.<your-subdomain>.workers.dev/api/mailboxes' -H 'x-api-key: ***'

# 统计
curl 'https://<your-worker>.<your-subdomain>.workers.dev/api/stats' -H 'x-api-key: ***'
```

### DELETE 接口

```bash
# 删除单封
curl -X DELETE 'https://<your-worker>.<your-subdomain>.workers.dev/api/email/<message_id>' \
  -H 'x-api-key: ***'

# 清空某地址下所有邮件
curl -X DELETE 'https://<your-worker>.<your-subdomain>.workers.dev/api/emails/clear?email=<addr>@mail.<your-domain>' \
  -H 'x-api-key: ***'
```

---

## 可选扩展

webhook 路径独立于以下三项。需要时启用即可。

### 扩展 A — 通过 Email Routing 接收真实 SMTP

使 worker 能够接收真实 SMTP 服务器投递到 `xxx@mail.<你的域名>` 的邮件。

1. 将域名添加到 Cloudflare，且 DNS 已在 CF 托管。
2. 在 `wrangler.toml` 中加入路由：
   ```toml
   [[routes]]
   pattern = "api.<你的域名>/*"
   zone_name = "<你的域名>"
   ```
3. 设置 `[vars] MAIL_DOMAIN = "mail.<你的域名>"`。
4. 在 Cloudflare 控制台对应 zone 下：**Email → Email Routing → Enable**，然后添加 catch-all 路由 `*@mail.<你的域名>` → **Send to Worker** → `cf-mail-api`。

真实 SMTP 投递的消息由 Cloudflare 分发给 worker，并经与 webhook 相同的路径写入 D1。

### 扩展 B — 转发到真实邮箱

在 `wrangler.toml` 中：

```toml
[vars]
FORWARD_TO_EMAIL = "you@gmail.com"
```

worker 读取该变量并将其作为每封入站邮件副本的目标地址。副本的实际投递由 worker 代码中接入的转发器完成；该变量只声明目标地址。

### 扩展 C — 通过 Resend 发件

添加第三个路由 `send.<你的域名>` 并设置 Resend API key：

```toml
[vars]
RESEND_API_KEY = "***"
```

```bash
curl -X POST https://send.<你的域名>/api/send \
  -H 'x-api-key: ***' \
  -H 'Content-Type: application/json' \
  -d '{
    "from":    "task_demo01@mail.<你的域名>",
    "to":      "bob@example.org",
    "subject": "你好",
    "text":    "通过 cf-mail-api 发送"
  }'
```

`from` 必须引用 D1 中已存在的 mailbox。域名需具备合法的 SPF/DKIM 记录以保证送达率。

---

## 配置参考

| 变量 | 是否必需 | 用途 |
|---|---|---|
| `API_TOKEN` | 是 | API Bearer token。使用 `openssl rand -hex 32` 生成。 |
| `MAIL_DOMAIN` | 否 | 生成 mailbox 地址时使用的展示域名，不参与路由。 |
| `FORWARD_TO_EMAIL` | 否 | 转发副本的目标地址。扩展 B。 |
| `RESEND_API_KEY` | 否 | 发件服务商 key。扩展 C。 |

---

## 成本与配额

worker 设计为完全运行在 Cloudflare 免费额度内：

| 资源 | 免费额度 |
|---|---|
| Workers 请求 | 100,000 / 天 |
| D1 读 | 5,000,000 / 天 |
| D1 写 | 100,000 / 天 |
| Email Routing 邮件 | 100 / 天 / 目标地址（仅扩展 A） |

鉴权开关存在但仅能防止未鉴权访问，不能阻止 token 泄露。worker URL 一旦公开，免费额度会被耗尽，部署对所有者本人也不再可用。

---

## 仓库规则

`lingion/cf-mail-api` 是本项目的唯一主线仓库。镜像与 fork 不应被视为主要入口。所有开发在此处合并。

---

## 文档

- `README.md` — English documentation
- `README.zh.md` — 中文文档（本文件）
- `RESEND_SETUP.md` — 历史性 Resend / 发件配置说明
- `schema.sql` — D1 数据库结构参考

---

## 许可证

GNU 通用公共许可证 v3.0。详见 [LICENSE](./LICENSE)。

你可以使用、修改、再分发本作品，包括用于商业目的，前提是衍生作品同样以 GPL-3.0 授权并保留版权声明。不提供任何担保。

---

## 贡献

欢迎在 <https://github.com/lingion/cf-mail-api> 提交 PR。提交贡献即视为同意以 GPL-3.0 授权你的贡献。