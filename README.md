# cf-mail-api

> Self-hosted temporary mailbox service on **Cloudflare Workers + D1** with your own custom subdomain.
> Use it as a personal disposable-mailbox backend — generate any `xxx@<your-domain>` on the fly, read incoming mail, forward to your real inbox.

[中文文档](./README.zh-CN.md)

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
- Bearer-token / `x-api-key` / `?api_key=*** auth
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

The **mailbox receiving domain** (`mail.<your-domain>`), the **API domain** (`api.<your-domain>`), and the **send domain** (`send.<your-domain>`) should all live under one zone you control.

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
> `Authorization: Bearer <API_TOKEN>` · `x-api-key: ***` · `?api_key=<API_TOKEN>`

### Health check

```bash
curl https://api.<your-domain>/health
```

### Generate a mailbox

```bash
curl -X POST https://api.<your-domain>/api/generate-email \
  -H 'x-api-key: ***' \
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
    "token": "***",
    "created_at": "...",
    "expires_at": "..."
  }
}
```

### List messages for a mailbox

```bash
curl 'https://api.<your-domain>/api/mailboxes/<mailbox_id>/messages' \
  -H 'x-api-key: ***'
```

### Fetch / delete a single message

```bash
curl 'https://api.<your-domain>/api/email/<message_id>'  -H 'x-api-key: ***'
curl -X DELETE 'https://api.<your-domain>/api/email/<message_id>' -H 'x-api-key: ***'
```

### Clear all mail for an address

```bash
curl -X DELETE 'https://api.<your-domain>/api/emails/clear?email=<addr>@mail.<your-domain>' \
  -H 'x-api-key: ***'
```

### Stats

```bash
curl 'https://api.<your-domain>/api/stats' -H 'x-api-key: ***'
```

### Inbound webhook (for external senders)

```bash
curl -X POST 'https://api.<your-domain>/api/inbound' \
  -H 'x-api-key: ***' \
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
RESEND_API_KEY = "<your-re…key>"
```

Then:

```bash
curl -X POST https://send.<your-domain>/api/send \
  -H 'x-api-key: ***' \
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
├── README.md            # this file (English)
├── README.zh-CN.md      # 中文文档
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