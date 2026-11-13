# ⚡ Jibsz Stunnel (VPS NAT & Cloudflare Argo Tunnel Edition)

**Jibsz Stunnel** adalah autoscript multi-protokol lengkap (**SSH WebSocket, VLESS, VMess, Trojan, Shadowsocks, & Bot Telegram Control Panel**) yang dioptimalkan khusus untuk **VPS NAT (tanpa IP publik dedicated / tanpa port inbound terbuka)** menggunakan **Token Cloudflare Tunnel (Argo)** maupun VPS Reguler.

Dibangun dan dikelola oleh **@admj1btnl (Jibsz)**.

## ✨ Fitur Utama
- **Cloudflare Tunnel Token Ready (`cloudflared`)**: Tidak perlu port forwarding 80/443 di panel VPS NAT. Cukup masukkan **Token Tunnel Cloudflare** saat instalasi atau melalui menu `[05] CF TUNNEL/BOT`.
- **Single Local Entrypoint (`127.0.0.1:8088`)**: Seluruh protokol berjalan secara lokal dan dipisahkan berdasarkan path oleh Nginx & Xray:
  - `/vless` → Xray VLESS WebSocket (`127.0.0.1:10001`)
  - `/vmess` → Xray VMess WebSocket (`127.0.0.1:10002`)
  - `/trojan-ws` → Xray Trojan WebSocket (`127.0.0.1:10003`)
  - `/ss-ws` → Xray Shadowsocks WebSocket (`127.0.0.1:10004`)
  - `/ssh-ws` atau `/` → ePro SSH WebSocket (`127.0.0.1:10015` → Dropbear `127.0.0.1:109`)
- **Bot Telegram Control Panel (`jibsz-bot`)**: Berjalan dengan hak akses *least-privilege* (`jibszbot`), mendukung manajemen `ADMIN_ID` & `AUTHORIZED_IDS`, serta perintah `/create`, `/myaccount`, `/listusers`, `/deluser`, `/adduser`, `/revoke`, `/tunnel`, dan `/restart`.
- **Dual-Mode Fleksibel**: Mendukung download langsung dari repositori GitHub Anda (cukup ubah variabel `REPO` saat eksekusi) maupun instalasi langsung dari hasil `git clone`.

## 🛠️ Persiapan di Dashboard Cloudflare Zero Trust (Wajib untuk VPS NAT)
1. Buka [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels**.
2. Klik **Create a tunnel** → Pilih **Cloudflared** → Beri nama (misal: `jibsz-stunnel-nat`) → Salin **Token Tunnel** (`eyJhIjoi...`).
3. Pada tab **Public Hostname**, tambahkan:
   - **Subdomain & Domain**: (misal `stunnel.domainanda.com`)
   - **Service Type**: `HTTP`
   - **URL**: `127.0.0.1:8088`
4. Di menu **SSL/TLS** Cloudflare domain Anda, aktifkan tab **Network** → **WebSockets: ON** dan **gRPC: ON**.

## 🚀 Cara Upload ke GitHub & Instalasi 1 Baris di VPS NAT

### Opsi A: Clone & Install Langsung dari GitHub Anda
Setelah seluruh isi folder ini di-upload ke repositori GitHub Anda (contoh: `https://github.com/mohamadrojib278/jibsz-stunnel`):

```bash
apt update && apt install -y git curl wget && \
git clone https://github.com/mohamadrojib278/jibsz-stunnel.git /root/jibsz-stunnel && \
chmod +x /root/jibsz-stunnel/setup.sh && \
/root/jibsz-stunnel/setup.sh
```

### Opsi B: One-Liner Installer via Raw GitHub
```bash
REPO="https://raw.githubusercontent.com/mohamadrojib278/jibsz-stunnel/main/" \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/mohamadrojib278/jibsz-stunnel/main/setup.sh)"
```

## 🖥️ Perintah Menu Setelah Instalasi
Ketik `menu` di terminal VPS untuk membuka dashboard **Jibsz Stunnel**, atau ketik `m-cf` untuk langsung membuka pengaturan **Token Cloudflare Tunnel & Bot Telegram**.
