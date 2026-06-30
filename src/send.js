#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# send.<your-domain> — Temporary Email Send Page
# Called from cf-mail-api worker at POST /api/send
# ============================================================================

# ── Send email via Resend API ──
# Usage: send_email(from, to, subject, text, html, reply_to, api_key)

SEND_EMAIL_HANDLER << 'EOF'
async function sendEmailViaResend({ from, to, subject, text, html, replyTo }, apiKey) {
  const body = {
    from,
    to: [to],
    subject,
  };
  if (text) body.text = text;
  if (html) body.html = html;
  if (replyTo) body.reply_to = replyTo;

  const resp = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(`Resend error: ${data?.message || JSON.stringify(data)}`);
  }
  return data;
}
EOF
