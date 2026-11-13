#!/usr/bin/env python3
# ==============================================================================
#  JIBSZ STUNNEL - TELEGRAM BOT CONTROL PANEL (VPS NAT & CLOUDFLARE TUNNEL)
#  Author / Credit : @admj1btnl (Jibsz)
#  Kompatibel dengan database /etc/xray/config.json & /etc/ssh/.ssh.db
# ==============================================================================

import base64
import datetime
import json
import logging
import os
import re
import subprocess
import time
import urllib.parse
import uuid
from typing import Dict, List, Optional, Set, Tuple

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [JIBSZ-STUNNEL-BOT] %(levelname)s: %(message)s",
)

BOT_ENV_PATH = os.environ.get("BOT_ENV_PATH", "/etc/jibsz-stunnel/bot.env")
HELPER_BIN = "/usr/local/bin/jibsz-helper"
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


def load_env(env_path: str = BOT_ENV_PATH) -> Dict[str, str]:
    config: Dict[str, str] = {}
    if not os.path.exists(env_path):
        return config
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip().strip('"').strip("'")
    return config


def save_env_key(key: str, value: str, env_path: str = BOT_ENV_PATH) -> None:
    lines: List[str] = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f'{key}="{value}"\n')
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f'{key}="{value}"\n')
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.chmod(env_path, 0o600)


def get_access_control() -> Tuple[int, Set[int], bool]:
    env = load_env()
    admin_id = int(env.get("ADMIN_ID", "0") or "0")
    raw_auth = env.get("AUTHORIZED_IDS", "")
    auth_ids: Set[int] = {admin_id} if admin_id else set()
    for item in raw_auth.split(","):
        item = item.strip()
        if item.isdigit():
            auth_ids.add(int(item))
    allow_user_create = env.get("ALLOW_USER_CREATE", "true").lower() == "true"
    return admin_id, auth_ids, allow_user_create


def is_admin(user_id: int) -> bool:
    admin_id, _, _ = get_access_control()
    return user_id == admin_id and admin_id != 0


def is_authorized(user_id: int) -> bool:
    _, auth_ids, _ = get_access_control()
    return user_id in auth_ids


def add_authorized_id(target_id: int) -> bool:
    _, auth_ids, _ = get_access_control()
    if target_id in auth_ids:
        return False
    auth_ids.add(target_id)
    save_env_key("AUTHORIZED_IDS", ",".join(str(x) for x in sorted(auth_ids)))
    return True


def revoke_authorized_id(target_id: int) -> bool:
    admin_id, auth_ids, _ = get_access_control()
    if target_id == admin_id or target_id not in auth_ids:
        return False
    auth_ids.remove(target_id)
    save_env_key("AUTHORIZED_IDS", ",".join(str(x) for x in sorted(auth_ids)))
    return True


def get_domain() -> str:
    if os.path.exists("/etc/xray/domain"):
        with open("/etc/xray/domain", "r", encoding="utf-8") as f:
            d = f.read().strip()
            if d:
                return d
    env = load_env()
    return env.get("TUNNEL_HOST", "localhost")


def generate_links(username: str, user_uuid: str, proto: str) -> Dict[str, str]:
    host = get_domain()
    links: Dict[str, str] = {}
    if proto in ("all", "vless"):
        links["vless_tls"] = (
            f"vless://{user_uuid}@{host}:443?encryption=none&security=tls"
            f"&sni={host}&type=ws&host={host}&path=%2Fvless#{username}-WS-TLS"
        )
        links["vless_ntls"] = (
            f"vless://{user_uuid}@{host}:80?encryption=none&security=none"
            f"&type=ws&host={host}&path=%2Fvless#{username}-WS-NTLS"
        )
    if proto in ("all", "vmess"):
        vmess_tls = {
            "v": "2",
            "ps": f"{username}-WS-TLS",
            "add": host,
            "port": "443",
            "id": user_uuid,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": host,
            "path": "/vmess",
            "tls": "tls",
            "sni": host,
        }
        b64 = base64.b64encode(json.dumps(vmess_tls, separators=(",", ":")).encode()).decode()
        links["vmess_tls"] = f"vmess://{b64}"
    if proto in ("all", "trojan"):
        links["trojan_ws"] = (
            f"trojan://{user_uuid}@{host}:443?security=tls&sni={host}"
            f"&type=ws&host={host}&path=%2Ftrojan-ws#{username}-TROJAN"
        )
    if proto in ("all", "ssh"):
        links["ssh_ws"] = (
            f"Host/SNI : {host}\n"
            f"Port     : 443 (TLS) / 80 (Non-TLS)\n"
            f"Username : {username}\n"
            f"Password : {user_uuid[:10]}\n"
            f"Payload  : GET /ssh-ws HTTP/1.1[crlf]Host: {host}[crlf]Upgrade: websocket[crlf]Connection: Upgrade[crlf][crlf]"
        )
    return links


def send_msg(token: str, chat_id: int, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
    except Exception as exc:
        logging.error(f"Telegram send error: {exc}")


def handle_command(token: str, chat_id: int, user_id: int, text: str) -> None:
    if not is_authorized(user_id):
        send_msg(
            token,
            chat_id,
            f"⛔ <b>Akses Ditolak!</b>\nID Telegram Anda (<code>{user_id}</code>) belum diotorisasi di <b>Jibsz Stunnel</b>.",
        )
        return

    parts = text.strip().split()
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]
    admin_flag = is_admin(user_id)
    _, auth_ids, allow_user_create = get_access_control()
    host = get_domain()

    if cmd in ("/start", "/help"):
        role = "👑 ADMIN UTAMA" if admin_flag else "✅ AUTHORIZED USER"
        msg = (
            f"⚡ <b>JIBSZ STUNNEL - BOT CONTROL PANEL</b> ⚡\n"
            f"Role: <b>{role}</b> (ID: <code>{user_id}</code>)\n"
            f"Domain Tunnel: <code>{host}</code>\n\n"
            "<b>Perintah Akun & Tunnel:</b>\n"
            "• /create <code>&lt;user&gt; &lt;vless|vmess|trojan|ssh|all&gt; [hari=30]</code>\n"
            "• /myaccount — Lihat daftar akun yang Anda buat\n"
            "• /tunnel — Info Hostname Cloudflare Tunnel & Path WebSocket\n"
        )
        if admin_flag:
            msg += (
                "\n<b>Perintah Khusus Admin:</b>\n"
                "• /listusers — Lihat semua akun terdaftar di Xray & SSH\n"
                "• /deluser <code>&lt;username&gt;</code> — Hapus akun\n"
                "• /adduser <code>&lt;id_telegram&gt;</code> — Tambah Authorized User\n"
                "• /revoke <code>&lt;id_telegram&gt;</code> — Cabut akses Authorized User\n"
                "• /authlist — Lihat daftar ID Telegram berwenang\n"
                "• /restart — Restart Xray, Nginx & Cloudflare Tunnel\n"
            )
        send_msg(token, chat_id, msg)

    elif cmd == "/tunnel":
        res = subprocess.run(["sudo", "-n", HELPER_BIN, "status"], capture_output=True, text=True, timeout=10, shell=False)
        st = res.stdout.strip() if res.returncode == 0 else "N/A"
        msg = (
            "🌐 <b>INFO JIBSZ STUNNEL (CLOUDFLARE ARGO NAT)</b>\n\n"
            f"• <b>Domain / Host :</b> <code>{host}</code>\n"
            "• <b>Target Lokal  :</b> <code>http://127.0.0.1:8088</code>\n"
            "• <b>Path VLESS WS :</b> <code>/vless</code>\n"
            "• <b>Path VMess WS :</b> <code>/vmess</code>\n"
            "• <b>Path Trojan   :</b> <code>/trojan-ws</code>\n"
            "• <b>Path SS WS    :</b> <code>/ss-ws</code>\n"
            "• <b>Path SSH WS   :</b> <code>/ssh-ws</code> (atau <code>/</code>)\n\n"
            f"<b>Status Service:</b>\n<pre>{st}</pre>"
        )
        send_msg(token, chat_id, msg)

    elif cmd == "/create":
        if not admin_flag and not allow_user_create:
            send_msg(token, chat_id, "⛔ Pembuatan akun mandiri sedang dinonaktifkan oleh Admin.")
            return
        if len(args) < 2:
            send_msg(token, chat_id, "⚠️ Gunakan: <code>/create &lt;username&gt; &lt;vless|vmess|trojan|ssh|all&gt; [hari=30]</code>")
            return
        uname = args[0]
        proto = args[1].lower()
        days = args[2] if len(args) >= 3 and args[2].isdigit() else "30"
        if not USERNAME_REGEX.match(uname):
            send_msg(token, chat_id, "⚠️ Username hanya boleh huruf/angka/underscore (3-20 karakter).")
            return
        if proto not in ("vless", "vmess", "trojan", "ssh", "all"):
            send_msg(token, chat_id, "⚠️ Pilih protokol: <code>vless | vmess | trojan | ssh | all</code>")
            return

        new_uuid = str(uuid.uuid4())
        res = subprocess.run(
            ["sudo", "-n", HELPER_BIN, "create-user", uname, proto, new_uuid, days, str(user_id)],
            capture_output=True,
            text=True,
            timeout=20,
            shell=False,
        )
        if res.returncode != 0:
            send_msg(token, chat_id, f"❌ Gagal membuat akun: {res.stderr.strip() or res.stdout.strip()}")
            return

        exp_date = (datetime.date.today() + datetime.timedelta(days=int(days))).isoformat()
        links = generate_links(uname, new_uuid, proto)
        out = [
            "✅ <b>AKUN JIBSZ STUNNEL BERHASIL DIBUAT</b>\n",
            f"👤 <b>Username :</b> <code>{uname}</code>",
            f"🔑 <b>UUID/Pass:</b> <code>{new_uuid}</code>",
            f"🌐 <b>Domain   :</b> <code>{host}</code>",
            f"📅 <b>Expired  :</b> <code>{exp_date} ({days} Hari)</code>\n",
        ]
        if "vless_tls" in links:
            out.append(f"🔗 <b>VLESS WS TLS (443):</b>\n<code>{links['vless_tls']}</code>\n")
        if "vmess_tls" in links:
            out.append(f"🔗 <b>VMess WS TLS (443):</b>\n<code>{links['vmess_tls']}</code>\n")
        if "trojan_ws" in links:
            out.append(f"🔗 <b>Trojan WS TLS (443):</b>\n<code>{links['trojan_ws']}</code>\n")
        if "ssh_ws" in links:
            out.append(f"🔗 <b>SSH WebSocket:</b>\n<pre>{links['ssh_ws']}</pre>")
        send_msg(token, chat_id, "\n".join(out))

    elif cmd in ("/myaccount", "/listusers"):
        if cmd == "/listusers" and not admin_flag:
            send_msg(token, chat_id, "⛔ Hanya Admin yang dapat melihat seluruh akun.")
            return
        db_path = "/etc/jibsz-stunnel/users_db.json"
        if not os.path.exists(db_path):
            send_msg(token, chat_id, "📂 Belum ada akun yang dibuat melalui Bot.")
            return
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)
        users = db.get("users", [])
        if cmd == "/myaccount" and not admin_flag:
            users = [u for u in users if int(u.get("owner_id", 0)) == user_id]
        if not users:
            send_msg(token, chat_id, "📂 Tidak ada akun ditemukan.")
            return
        for u in users:
            links = generate_links(u["username"], u["uuid"], u["protocol"])
            txt = (
                f"👤 <b>{u['username']}</b> ({u['protocol'].upper()}) | Exp: <code>{u['expires_at']}</code>\n"
                f"UUID: <code>{u['uuid']}</code>\n"
            )
            if "vless_tls" in links:
                txt += f"VLESS: <code>{links['vless_tls']}</code>\n"
            if "vmess_tls" in links:
                txt += f"VMess: <code>{links['vmess_tls']}</code>\n"
            if "trojan_ws" in links:
                txt += f"Trojan: <code>{links['trojan_ws']}</code>\n"
            send_msg(token, chat_id, txt)

    elif cmd == "/deluser":
        if not admin_flag:
            send_msg(token, chat_id, "⛔ Perintah khusus Admin.")
            return
        if not args or not USERNAME_REGEX.match(args[0]):
            send_msg(token, chat_id, "⚠️ Gunakan: <code>/deluser &lt;username&gt;</code>")
            return
        res = subprocess.run(["sudo", "-n", HELPER_BIN, "delete-user", args[0]], capture_output=True, text=True, timeout=15, shell=False)
        if res.returncode == 0:
            send_msg(token, chat_id, f"✅ Akun <code>{args[0]}</code> berhasil dihapus.")
        else:
            send_msg(token, chat_id, f"❌ Gagal menghapus akun: {res.stderr.strip()}")

    elif cmd == "/adduser":
        if not admin_flag:
            send_msg(token, chat_id, "⛔ Perintah khusus Admin.")
            return
        if not args or not args[0].isdigit():
            send_msg(token, chat_id, "⚠️ Gunakan: <code>/adduser &lt;id_telegram&gt;</code>")
            return
        tid = int(args[0])
        if add_authorized_id(tid):
            send_msg(token, chat_id, f"✅ ID <code>{tid}</code> berhasil ditambahkan ke AUTHORIZED_IDS.")
        else:
            send_msg(token, chat_id, f"ℹ️ ID <code>{tid}</code> sudah terdaftar.")

    elif cmd == "/revoke":
        if not admin_flag:
            send_msg(token, chat_id, "⛔ Perintah khusus Admin.")
            return
        if not args or not args[0].isdigit():
            send_msg(token, chat_id, "⚠️ Gunakan: <code>/revoke &lt;id_telegram&gt;</code>")
            return
        tid = int(args[0])
        if revoke_authorized_id(tid):
            send_msg(token, chat_id, f"✅ Akses ID <code>{tid}</code> berhasil dicabut.")
        else:
            send_msg(token, chat_id, "❌ Gagal mencabut akses (ID tidak ditemukan atau merupakan Admin Utama).")

    elif cmd == "/authlist":
        if not admin_flag:
            send_msg(token, chat_id, "⛔ Perintah khusus Admin.")
            return
        aid_val, aset, _ = get_access_control()
        lines = "\n".join(f"• <code>{x}</code> {'(Admin)' if x == aid_val else '(Authorized)'}" for x in sorted(aset))
        send_msg(token, chat_id, f"🔐 <b>Daftar Pengguna Berwenang:</b>\n{lines}")

    elif cmd == "/restart":
        if not admin_flag:
            send_msg(token, chat_id, "⛔ Perintah khusus Admin.")
            return
        subprocess.run(["sudo", "-n", HELPER_BIN, "restart"], capture_output=True, text=True, timeout=20, shell=False)
        send_msg(token, chat_id, "✅ Seluruh service (Xray, Nginx, WS, Cloudflare Tunnel) berhasil direstart.")


def main() -> None:
    while True:
        env = load_env()
        token = env.get("BOT_TOKEN", "")
        if not token or token == "ISI_DENGAN_TOKEN_BOTFATHER":
            time.sleep(15)
            continue
        offset = 0
        base_url = f"https://api.telegram.org/bot{token}"
        logging.info("Jibsz Stunnel Telegram Bot Polling aktif...")
        while True:
            try:
                resp = requests.get(f"{base_url}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
                if resp.status_code == 200:
                    for upd in resp.json().get("result", []):
                        offset = upd["update_id"] + 1
                        msg = upd.get("message")
                        if msg and "text" in msg and msg["text"].startswith("/"):
                            handle_command(token, msg["chat"]["id"], msg.get("from", {}).get("id", 0), msg["text"])
                else:
                    time.sleep(5)
            except Exception as exc:
                logging.warning(f"Polling retry: {exc}")
                time.sleep(5)


if __name__ == "__main__":
    main()
