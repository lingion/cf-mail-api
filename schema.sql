CREATE TABLE IF NOT EXISTS mailboxes (
  id TEXT PRIMARY KEY,
  address TEXT NOT NULL UNIQUE,
  token TEXT NOT NULL UNIQUE,
  label TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  max_messages INTEGER NOT NULL DEFAULT 5
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  mailbox_id TEXT NOT NULL,
  external_id TEXT,
  from_addr TEXT,
  to_addr TEXT,
  subject TEXT,
  text_body TEXT,
  html_body TEXT,
  raw_json TEXT,
  received_at TEXT NOT NULL,
  FOREIGN KEY(mailbox_id) REFERENCES mailboxes(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_mailbox_id ON messages(mailbox_id);
CREATE INDEX IF NOT EXISTS idx_messages_received_at ON messages(received_at);

CREATE TABLE IF NOT EXISTS sent_messages (
  id TEXT PRIMARY KEY,
  from_address TEXT NOT NULL,
  to_address TEXT NOT NULL,
  subject TEXT,
  text_body TEXT,
  html_body TEXT,
  provider TEXT,
  provider_message_id TEXT,
  status TEXT NOT NULL DEFAULT 'sent',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sent_from ON sent_messages(from_address);
CREATE INDEX IF NOT EXISTS idx_sent_created ON sent_messages(created_at);
