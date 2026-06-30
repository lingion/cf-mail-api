import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import requests

CF_MAIL_BASE = os.environ.get("CF_MAIL_BASE", "https://api.<your-domain>")
CF_MAIL_API_KEY = os.environ.get("CF_MAIL_API_KEY", "<your-api-token>")


def _cf_mail_headers(*, api_key: str = CF_MAIL_API_KEY, use_json: bool = False) -> Dict[str, Any]:
    headers = {"Accept": "application/json", "x-api-key": api_key}
    if use_json:
        headers["Content-Type"] = "application/json"
    return headers


def create_cf_mailbox(
    prefix: str = "",
    *,
    label: str = "",
    ttl_minutes: int = 10,
    max_messages: int = 5,
    api_key: str = CF_MAIL_API_KEY,
    proxies: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    创建 Cloudflare 临时邮箱。

    返回: (email, full_response_data)
    """
    payload: Dict[str, Any] = {
        "label": label or None,
        "ttl_minutes": ttl_minutes,
        "max_messages": max_messages,
    }
    if prefix:
        payload["prefix"] = prefix

    resp = requests.post(
        f"{CF_MAIL_BASE}/api/generate-email",
        headers=_cf_mail_headers(api_key=api_key, use_json=True),
        json=payload,
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"创建 Cloudflare 邮箱失败: {resp.status_code} {resp.text[:300]}")

    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"创建 Cloudflare 邮箱失败: {data}")

    mailbox = data.get("data") or {}
    email = str(mailbox.get("email") or mailbox.get("address") or "").strip()
    if not email:
        raise RuntimeError(f"创建成功但未返回邮箱地址: {data}")
    return email, mailbox


def list_cf_mailboxes(*, api_key: str = CF_MAIL_API_KEY, proxies: Any = None) -> Dict[str, Any]:
    resp = requests.get(
        f"{CF_MAIL_BASE}/api/mailboxes",
        headers=_cf_mail_headers(api_key=api_key),
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"获取邮箱列表失败: {resp.status_code} {resp.text[:300]}")
    return resp.json()



def list_cf_emails(email: str, *, api_key: str = CF_MAIL_API_KEY, proxies: Any = None) -> Dict[str, Any]:
    resp = requests.get(
        f"{CF_MAIL_BASE}/api/emails",
        headers=_cf_mail_headers(api_key=api_key),
        params={"email": email},
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"获取邮件列表失败: {resp.status_code} {resp.text[:300]}")
    return resp.json()



def get_cf_email_detail(message_id: int, *, api_key: str = CF_MAIL_API_KEY, proxies: Any = None) -> Dict[str, Any]:
    resp = requests.get(
        f"{CF_MAIL_BASE}/api/email/{message_id}",
        headers=_cf_mail_headers(api_key=api_key),
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"获取单封邮件失败: {resp.status_code} {resp.text[:300]}")
    return resp.json()



def delete_cf_email(message_id: int, *, api_key: str = CF_MAIL_API_KEY, proxies: Any = None) -> Dict[str, Any]:
    resp = requests.delete(
        f"{CF_MAIL_BASE}/api/email/{message_id}",
        headers=_cf_mail_headers(api_key=api_key),
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"删除单封邮件失败: {resp.status_code} {resp.text[:300]}")
    return resp.json()



def clear_cf_emails(email: str, *, api_key: str = CF_MAIL_API_KEY, proxies: Any = None) -> Dict[str, Any]:
    resp = requests.delete(
        f"{CF_MAIL_BASE}/api/emails/clear",
        headers=_cf_mail_headers(api_key=api_key),
        params={"email": email},
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"清空邮件失败: {resp.status_code} {resp.text[:300]}")
    return resp.json()



def get_cf_stats(*, api_key: str = CF_MAIL_API_KEY, proxies: Any = None) -> Dict[str, Any]:
    resp = requests.get(
        f"{CF_MAIL_BASE}/api/stats",
        headers=_cf_mail_headers(api_key=api_key),
        proxies=proxies,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"获取统计失败: {resp.status_code} {resp.text[:300]}")
    return resp.json()



def _extract_otp_or_link(content: str) -> str:
    link_regex = r'https?://[^\s"\'<>]+'
    code_regex = r'(?<!\d)(\d{6})(?!\d)'

    link_match = re.search(link_regex, content)
    if link_match:
        return link_match.group(0)

    code_match = re.search(code_regex, content)
    if code_match:
        return code_match.group(1)

    return ""



def poll_cf_oai_code(
    email: str,
    *,
    api_key: str = CF_MAIL_API_KEY,
    proxies: Any = None,
    seen_msg_ids: Optional[set] = None,
    max_rounds: int = 40,
    sleep_seconds: int = 3,
) -> str:
    """
    轮询 Cloudflare 临时邮箱，抓取 6 位验证码或验证链接。
    规则和 sub.txt 风格一致。
    """
    if seen_msg_ids is None:
        seen_msg_ids = set()

    print(f"[*] 正在等待 Cloudflare 邮箱 {email} 的验证码...", end="", flush=True)

    for _ in range(max_rounds):
        print(".", end="", flush=True)
        try:
            data = list_cf_emails(email, api_key=api_key, proxies=proxies)
            emails = ((data or {}).get("data") or {}).get("emails") or []
            for msg in emails:
                msg_id = str(msg.get("id") or "")
                if not msg_id or msg_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(msg_id)

                detail = get_cf_email_detail(int(msg_id), api_key=api_key, proxies=proxies)
                item = (detail.get("data") or {}) if isinstance(detail, dict) else {}
                sender = str(item.get("from_address") or "").lower()
                subject = str(item.get("subject") or "")
                body = str(item.get("content") or "")
                html = str(item.get("html_content") or "")
                content = "\n".join([sender, subject, body, html])

                # 这里沿用你原来的筛选思路，优先盯 OpenAI / Lingion 测试网址
                lowered = content.lower()
                if (
                    "openai" not in lowered
                    and "chatgpt" not in lowered
                    and "lingion 测试网址" not in lowered
                ):
                    continue

                result = _extract_otp_or_link(content)
                if result:
                    print(f" 抓到啦: {result}")
                    return result
        except Exception:
            pass

        time.sleep(sleep_seconds)

    print(" 超时，未收到验证码")
    return ""



def get_email_and_token_cloudflare(
    prefix: str = "",
    *,
    label: str = "",
    ttl_minutes: int = 10,
    max_messages: int = 5,
    api_key: str = CF_MAIL_API_KEY,
    proxies: Any = None,
) -> tuple:
    """
    模仿 sub.txt 的 get_email_and_token 风格。
    Cloudflare 这里没有单独 mailbox token 参与读信鉴权，统一用 API key。
    所以第二返回值给出一个 source 风格 token 标记。
    """
    email, mailbox = create_cf_mailbox(
        prefix,
        label=label,
        ttl_minutes=ttl_minutes,
        max_messages=max_messages,
        api_key=api_key,
        proxies=proxies,
    )
    mailbox_id = mailbox.get("mailbox_id") or ""
    return email, f"cloudflare:{mailbox_id}:{api_key}"


if __name__ == "__main__":
    email, token = get_email_and_token_cloudflare(prefix="cfdemo001", label="demo")
    print("email:", email)
    print("token:", token)
    print("stats:", get_cf_stats())
